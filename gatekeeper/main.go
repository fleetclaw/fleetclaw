// Gatekeeper - Permission Routing Sidecar for Fleetclaw
//
// Routes incoming Telegram webhooks through permission checks before
// forwarding to the OpenClaw agent. Enforces the permission matrix
// defined in permissions.yaml.
//
// Usage:
//   ASSET_ID=EX-001 AGENT_PORT=8080 ./gatekeeper
//
// Listens on port 8081 and forwards authorized requests to localhost:$AGENT_PORT.

package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"strings"
	"sync"
	"time"

	"github.com/fsnotify/fsnotify"
	"github.com/redis/go-redis/v9"
	"gopkg.in/yaml.v3"
)

// Intent detection keywords - maps intent names to trigger words
var intentKeywords = map[string][]string{
	"fuel_log":    {"fuel", "filled", "liters", "litres", "refuel"},
	"preop":       {"preop", "pre-op", "prestart", "checklist", "inspection"},
	"status":      {"status", "how is", "report"},
	"maintenance": {"maintenance", "service", "repair"},
	"escalate":    {"escalate", "urgent", "emergency", "supervisor"},
	"config":      {"config", "setting", "configure"},
	"shutdown":    {"shutdown", "stop", "halt"},
}

// Callback action prefixes - maps callback data prefixes to intents
var callbackIntents = map[string]string{
	"fuel":        "fuel_log",
	"preop":       "preop",
	"status":      "status",
	"confirm":     "general",
	"cancel":      "general",
	"maintenance": "maintenance",
	"escalate":    "escalate",
}

// Config holds the gatekeeper configuration
type Config struct {
	AssetID   string
	AgentPort string
	Users     UserRegistry
	Matrix    PermissionMatrix
}

// UserRegistry maps Telegram IDs to user info
type UserRegistry struct {
	Users []User `yaml:"users"`
}

// User represents a registered user
type User struct {
	Name       string   `yaml:"name"`
	TelegramID int64    `yaml:"telegram_id"`
	Roles      []string `yaml:"roles"`
	AssetIDs   []string `yaml:"asset_ids,omitempty"` // Empty = all assets
}

// PermissionMatrix defines role-based access control
type PermissionMatrix struct {
	Roles map[string]RolePermissions `yaml:"roles"`
}

// RolePermissions defines what a role can do
type RolePermissions struct {
	AllowedIntents  []string `yaml:"allowed_intents"`
	AllowedChannels []string `yaml:"allowed_channels"` // "private", "group", "all"
}

// TelegramUpdate represents an incoming Telegram webhook
type TelegramUpdate struct {
	UpdateID      int64            `json:"update_id"`
	Message       *TelegramMessage `json:"message,omitempty"`
	EditedMessage *TelegramMessage `json:"edited_message,omitempty"`
	CallbackQuery *CallbackQuery   `json:"callback_query,omitempty"`
	InlineQuery   *InlineQuery     `json:"inline_query,omitempty"`
	ChannelPost   *TelegramMessage `json:"channel_post,omitempty"`
}

// CallbackQuery represents a callback query from an inline keyboard
type CallbackQuery struct {
	ID      string           `json:"id"`
	From    *TelegramUser    `json:"from"`
	Message *TelegramMessage `json:"message,omitempty"`
	Data    string           `json:"data,omitempty"`
}

// InlineQuery represents an inline query
type InlineQuery struct {
	ID    string        `json:"id"`
	From  *TelegramUser `json:"from"`
	Query string        `json:"query"`
}

// TelegramMessage represents a Telegram message
type TelegramMessage struct {
	MessageID int64         `json:"message_id"`
	From      *TelegramUser `json:"from,omitempty"`
	Chat      *TelegramChat `json:"chat"`
	Text      string        `json:"text,omitempty"`
	Date      int64         `json:"date"`
}

// TelegramUser represents a Telegram user
type TelegramUser struct {
	ID        int64  `json:"id"`
	FirstName string `json:"first_name"`
	LastName  string `json:"last_name,omitempty"`
	Username  string `json:"username,omitempty"`
}

// TelegramChat represents a Telegram chat
type TelegramChat struct {
	ID    int64  `json:"id"`
	Type  string `json:"type"` // "private", "group", "supergroup"
	Title string `json:"title,omitempty"`
}

var (
	config       Config
	configMutex  sync.RWMutex
	redisClient  *redis.Client
	ctx          = context.Background()
)

// AssetInfo represents cached asset information from Redis
type AssetInfo struct {
	AssetID string `json:"asset_id"`
	Type    string `json:"type"`   // "agent", "tracked", "coordinator"
	Status  string `json:"status"` // "active", "idle" (for agents only)
}

// Redis key prefixes
const (
	keyGroupMap     = "fleet:group_map:%d"
	keyLifecycle    = "fleet:lifecycle:%s"
	keyWakeBuffer   = "fleet:wake_buffer:%s"
	wakeBufferTTL   = 300 // seconds
)

func main() {
	// Load configuration
	config.AssetID = os.Getenv("ASSET_ID")
	if config.AssetID == "" {
		log.Fatal("ASSET_ID environment variable required")
	}

	config.AgentPort = os.Getenv("AGENT_PORT")
	if config.AgentPort == "" {
		config.AgentPort = "8080"
	}

	// Initialize Redis client for idle management
	redisURL := os.Getenv("REDIS_URL")
	if redisURL != "" {
		opt, err := redis.ParseURL(redisURL)
		if err != nil {
			log.Printf("Warning: Could not parse REDIS_URL: %v", err)
		} else {
			redisClient = redis.NewClient(opt)
			if err := redisClient.Ping(ctx).Err(); err != nil {
				log.Printf("Warning: Redis connection failed: %v", err)
				redisClient = nil
			} else {
				log.Printf("Connected to Redis for idle management")
			}
		}
	}

	// Load user registry
	usersFile := os.Getenv("USERS_FILE")
	if usersFile == "" {
		usersFile = "/app/config/users.yaml"
	}
	if err := loadYAML(usersFile, &config.Users); err != nil {
		log.Printf("Warning: Could not load users.yaml: %v", err)
	}

	// Load permission matrix
	permFile := os.Getenv("PERMISSIONS_FILE")
	if permFile == "" {
		permFile = "/app/config/permissions.yaml"
	}
	if err := loadYAML(permFile, &config.Matrix); err != nil {
		log.Printf("Warning: Could not load permissions.yaml: %v", err)
	}

	// Start watching config files for hot-reload
	watchConfigFiles(usersFile, permFile)

	// Set up HTTP handlers
	http.HandleFunc("/webhook", handleWebhook)
	http.HandleFunc("/health", handleHealth)

	port := os.Getenv("GATEKEEPER_PORT")
	if port == "" {
		port = "8081"
	}

	log.Printf("Gatekeeper starting for asset %s on port %s", config.AssetID, port)
	log.Printf("Forwarding authorized requests to localhost:%s", config.AgentPort)

	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatal(err)
	}
}

func loadYAML(path string, v interface{}) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return yaml.Unmarshal(data, v)
}

func reloadConfigs(usersFile, permissionsFile string) {
	var newUsers UserRegistry
	var newMatrix PermissionMatrix

	if err := loadYAML(usersFile, &newUsers); err != nil {
		log.Printf("Failed to reload users: %v", err)
		return
	}
	if err := loadYAML(permissionsFile, &newMatrix); err != nil {
		log.Printf("Failed to reload permissions: %v", err)
		return
	}

	configMutex.Lock()
	config.Users = newUsers
	config.Matrix = newMatrix
	configMutex.Unlock()

	log.Printf("Configs reloaded: %d users, %d roles",
		len(newUsers.Users), len(newMatrix.Roles))
}

func watchConfigFiles(usersFile, permissionsFile string) {
	watcher, err := fsnotify.NewWatcher()
	if err != nil {
		log.Printf("Warning: Could not create config watcher: %v", err)
		return
	}

	go func() {
		var reloadTimer *time.Timer
		const debounceDelay = 100 * time.Millisecond

		for {
			select {
			case event, ok := <-watcher.Events:
				if !ok {
					return
				}
				if event.Op&fsnotify.Write == fsnotify.Write {
					// Debounce: file saves often trigger multiple write events
					if reloadTimer != nil {
						reloadTimer.Stop()
					}
					reloadTimer = time.AfterFunc(debounceDelay, func() {
						log.Printf("Config file changed: %s", event.Name)
						reloadConfigs(usersFile, permissionsFile)
					})
				}
			case err, ok := <-watcher.Errors:
				if !ok {
					return
				}
				log.Printf("Config watcher error: %v", err)
			}
		}
	}()

	if err := watcher.Add(usersFile); err != nil {
		log.Printf("Warning: Could not watch users file: %v", err)
	}
	if err := watcher.Add(permissionsFile); err != nil {
		log.Printf("Warning: Could not watch permissions file: %v", err)
	}
	log.Printf("Watching config files for changes")
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("OK"))
}

func handleWebhook(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Read body
	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Failed to read body", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	// Parse Telegram update
	var update TelegramUpdate
	if err := json.Unmarshal(body, &update); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	// Extract user, intent, and channel type from any update type
	telegramUser, intent, channelType, updateType := extractUpdateInfo(&update)

	// Get group ID for idle-aware routing
	groupID := extractGroupID(&update)

	// Check if this is for an idle asset (when gatekeeper is routing for multiple assets)
	if groupID != 0 && redisClient != nil {
		assetInfo, err := getAssetInfoByGroup(groupID)
		if err == nil && assetInfo != nil {
			// Check current status
			currentStatus := getAssetStatus(assetInfo.AssetID)

			switch {
			case assetInfo.Type == "agent" && currentStatus == "idle":
				// Asset is idle - buffer message and wake
				handleIdleAsset(w, assetInfo.AssetID, body, groupID)
				return

			case assetInfo.Type == "tracked":
				// Tracked asset (no agent) - forward to FC
				log.Printf("Tracked asset %s message forwarded to FC", assetInfo.AssetID)
				forwardToFleetCoordinator(w, body, assetInfo.AssetID)
				return

			case assetInfo.Type == "coordinator":
				// FC message - forward directly
				log.Printf("Fleet Coordinator message")
				forwardToAgent(w, body)
				return
			}
		}
	}

	// If we couldn't extract user info, reject the update
	if telegramUser == nil {
		log.Printf("Rejected update: could not extract user info (type: %s)", updateType)
		respondUnauthorized(w, "Could not identify user")
		return
	}

	// Resolve user
	user := resolveUser(telegramUser.ID)
	if user == nil {
		log.Printf("Unauthorized user: %d (%s %s) via %s",
			telegramUser.ID,
			telegramUser.FirstName,
			telegramUser.LastName,
			updateType)
		respondUnauthorized(w, "User not registered")
		return
	}

	// Check asset access
	if !hasAssetAccess(user, config.AssetID) {
		log.Printf("User %s denied access to asset %s", user.Name, config.AssetID)
		respondUnauthorized(w, "No access to this asset")
		return
	}

	// Check permission
	if !hasPermission(user, intent, channelType) {
		log.Printf("User %s denied permission for intent '%s' on %s channel (via %s)",
			user.Name, intent, channelType, updateType)
		respondDenied(w, fmt.Sprintf("Permission denied for %s", intent))
		return
	}

	log.Printf("Authorized: user=%s, intent=%s, channel=%s, asset=%s, type=%s",
		user.Name, intent, channelType, config.AssetID, updateType)

	// Forward to agent
	forwardToAgent(w, body)
}

// forwardToFleetCoordinator forwards a message to Fleet Coordinator
func forwardToFleetCoordinator(w http.ResponseWriter, body []byte, sourceAssetID string) {
	fcPort := os.Getenv("FC_PORT")
	if fcPort == "" {
		fcPort = "8080"
	}

	fcHost := os.Getenv("FC_HOST")
	if fcHost == "" {
		fcHost = "fleetclaw-fleet-coord"
	}

	url := fmt.Sprintf("http://%s:%s/webhook", fcHost, fcPort)
	forwardRequest(w, body, url, "FC")
}

func channelTypeFromChat(chat *TelegramChat) string {
	if chat != nil {
		return chat.Type
	}
	return "private"
}

func extractUpdateInfo(update *TelegramUpdate) (*TelegramUser, string, string, string) {
	// Message (most common)
	if update.Message != nil && update.Message.From != nil {
		return update.Message.From,
			detectIntent(update.Message.Text),
			channelTypeFromChat(update.Message.Chat),
			"message"
	}

	// Edited message
	if update.EditedMessage != nil && update.EditedMessage.From != nil {
		return update.EditedMessage.From,
			detectIntent(update.EditedMessage.Text),
			channelTypeFromChat(update.EditedMessage.Chat),
			"edited_message"
	}

	// Callback query (inline keyboard button press)
	if update.CallbackQuery != nil && update.CallbackQuery.From != nil {
		intent := detectIntentFromCallback(update.CallbackQuery.Data)
		channelType := channelTypeFromCallbackMessage(update.CallbackQuery.Message)
		return update.CallbackQuery.From, intent, channelType, "callback_query"
	}

	// Inline query (always from private context)
	if update.InlineQuery != nil && update.InlineQuery.From != nil {
		intent := "inline_query"
		if update.InlineQuery.Query != "" {
			intent = detectIntent(update.InlineQuery.Query)
		}
		return update.InlineQuery.From, intent, "private", "inline_query"
	}

	// Channel post - return nil user since channel posts may be from anonymous admins
	if update.ChannelPost != nil {
		return nil, "channel_post", channelTypeFromChat(update.ChannelPost.Chat), "channel_post"
	}

	return nil, "unknown", "unknown", "unknown"
}

func channelTypeFromCallbackMessage(msg *TelegramMessage) string {
	if msg != nil && msg.Chat != nil {
		return msg.Chat.Type
	}
	return "private"
}

// extractGroupID returns the chat ID from any update type that contains a chat
func extractGroupID(update *TelegramUpdate) int64 {
	if update.Message != nil && update.Message.Chat != nil {
		return update.Message.Chat.ID
	}
	if update.CallbackQuery != nil && update.CallbackQuery.Message != nil && update.CallbackQuery.Message.Chat != nil {
		return update.CallbackQuery.Message.Chat.ID
	}
	return 0
}

func detectIntentFromCallback(data string) string {
	if data == "" {
		return "callback"
	}
	normalized := strings.ToLower(strings.TrimSpace(data))
	for prefix, intent := range callbackIntents {
		if strings.HasPrefix(normalized, prefix) {
			return intent
		}
	}
	return "callback"
}

func resolveUser(telegramID int64) *User {
	configMutex.RLock()
	defer configMutex.RUnlock()
	for _, u := range config.Users.Users {
		if u.TelegramID == telegramID {
			userCopy := u
			return &userCopy
		}
	}
	return nil
}

func hasAssetAccess(user *User, assetID string) bool {
	// Empty asset list = access to all
	if len(user.AssetIDs) == 0 {
		return true
	}
	for _, id := range user.AssetIDs {
		if id == assetID || id == "*" {
			return true
		}
	}
	return false
}

func detectIntent(text string) string {
	text = strings.ToLower(strings.TrimSpace(text))

	// Command-based intents (e.g., "/status" -> "status")
	if strings.HasPrefix(text, "/") {
		parts := strings.Fields(text)
		return strings.TrimPrefix(parts[0], "/")
	}

	// Keyword-based intent detection
	for intent, words := range intentKeywords {
		for _, word := range words {
			if strings.Contains(text, word) {
				return intent
			}
		}
	}

	return "general"
}

func hasPermission(user *User, intent string, channelType string) bool {
	configMutex.RLock()
	defer configMutex.RUnlock()
	for _, role := range user.Roles {
		perms, ok := config.Matrix.Roles[role]
		if !ok {
			continue
		}

		// Check channel type
		channelAllowed := false
		for _, ch := range perms.AllowedChannels {
			if ch == "all" || ch == channelType {
				channelAllowed = true
				break
			}
		}
		if !channelAllowed {
			continue
		}

		// Check intent
		for _, allowed := range perms.AllowedIntents {
			if allowed == "*" || allowed == intent {
				return true
			}
		}
	}

	return false
}

// forwardRequest forwards a webhook to the specified URL and proxies the response
func forwardRequest(w http.ResponseWriter, body []byte, url string, targetName string) {
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Post(url, "application/json", bytes.NewReader(body))
	if err != nil {
		log.Printf("Error forwarding to %s: %v", targetName, err)
		http.Error(w, targetName+" unavailable", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	w.WriteHeader(resp.StatusCode)
	w.Write(respBody)
}

func forwardToAgent(w http.ResponseWriter, body []byte) {
	url := fmt.Sprintf("http://localhost:%s/webhook", config.AgentPort)
	forwardRequest(w, body, url, "agent")
}

// getAssetInfoByGroup looks up asset info from Redis group mapping
func getAssetInfoByGroup(groupID int64) (*AssetInfo, error) {
	if redisClient == nil {
		return nil, fmt.Errorf("redis not available")
	}

	key := fmt.Sprintf(keyGroupMap, groupID)
	data, err := redisClient.HGetAll(ctx, key).Result()
	if err != nil {
		return nil, err
	}
	if len(data) == 0 {
		return nil, fmt.Errorf("group not mapped")
	}

	return &AssetInfo{
		AssetID: data["asset_id"],
		Type:    data["type"],
		Status:  data["status"],
	}, nil
}

// getAssetStatus gets current status from Redis
func getAssetStatus(assetID string) string {
	if redisClient == nil {
		return "unknown"
	}

	status, err := redisClient.HGet(ctx, fmt.Sprintf(keyLifecycle, assetID), "status").Result()
	if err != nil {
		return "unknown"
	}
	return status
}

// bufferMessageForWake stores a message to be replayed when asset wakes
func bufferMessageForWake(assetID string, body []byte) error {
	if redisClient == nil {
		return fmt.Errorf("redis not available")
	}

	key := fmt.Sprintf(keyWakeBuffer, assetID)
	return redisClient.Set(ctx, key, string(body), time.Duration(wakeBufferTTL)*time.Second).Err()
}

// wakeAsset starts an idle asset's container
func wakeAsset(assetID string) error {
	composeFile := os.Getenv("COMPOSE_FILE")
	if composeFile == "" {
		composeFile = "/app/config/docker-compose.yml"
	}

	containerName := fmt.Sprintf("fleetclaw-%s", strings.ToLower(assetID))
	cmd := exec.Command("docker", "compose", "-f", composeFile, "start", containerName)
	output, err := cmd.CombinedOutput()
	if err != nil {
		log.Printf("Failed to wake %s: %v - %s", assetID, err, string(output))
		return err
	}

	// Update status in Redis
	if redisClient != nil {
		now := time.Now().UTC().Format(time.RFC3339)
		redisClient.HSet(ctx, fmt.Sprintf(keyLifecycle, assetID),
			"status", "active",
			"last_activity", now,
			"last_activity_type", "wake")
	}

	log.Printf("Woke asset %s", assetID)
	return nil
}

// handleIdleAsset handles a message destined for an idle asset
func handleIdleAsset(w http.ResponseWriter, assetID string, body []byte, groupID int64) {
	log.Printf("Asset %s is idle, buffering message and waking", assetID)

	// Buffer the message
	if err := bufferMessageForWake(assetID, body); err != nil {
		log.Printf("Failed to buffer message: %v", err)
	}

	// Send notification to group (would need Telegram bot token)
	// For now, just log it
	log.Printf("Waking %s, message buffered for replay", assetID)

	// Wake the asset
	go func() {
		if err := wakeAsset(assetID); err != nil {
			log.Printf("Failed to wake %s: %v", assetID, err)
		}
	}()

	// Respond with acknowledgment
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{
		"status":  "waking",
		"message": fmt.Sprintf("Waking %s, message queued for processing", assetID),
	})
}

func respondUnauthorized(w http.ResponseWriter, message string) {
	w.WriteHeader(http.StatusOK) // Telegram expects 200
	json.NewEncoder(w).Encode(map[string]string{
		"status":  "unauthorized",
		"message": message,
	})
}

func respondDenied(w http.ResponseWriter, message string) {
	w.WriteHeader(http.StatusOK) // Telegram expects 200
	json.NewEncoder(w).Encode(map[string]string{
		"status":  "denied",
		"message": message,
	})
}
