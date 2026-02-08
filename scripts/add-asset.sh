#!/bin/bash
# Add a new asset to the Fleetclaw fleet
#
# Usage: ./scripts/add-asset.sh
#
# This script interactively collects information about a new asset
# and appends it to fleet.yaml

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLEET_FILE="${SCRIPT_DIR}/../config/fleet.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo "  Fleetclaw - Add New Asset"
echo "======================================"
echo ""

# Check if fleet.yaml exists
if [ ! -f "$FLEET_FILE" ]; then
    echo -e "${YELLOW}fleet.yaml not found. Creating from template...${NC}"
    if [ -f "${FLEET_FILE}.example" ]; then
        cp "${FLEET_FILE}.example" "$FLEET_FILE"
        echo -e "${GREEN}Created fleet.yaml from example${NC}"
    else
        echo -e "${RED}Error: No fleet.yaml or fleet.yaml.example found${NC}"
        exit 1
    fi
fi

# Collect asset information
echo "Enter asset details:"
echo ""

read -p "Asset ID (e.g., EX-003, HT-045): " ASSET_ID
if [ -z "$ASSET_ID" ]; then
    echo -e "${RED}Error: Asset ID is required${NC}"
    exit 1
fi

# Check if asset already exists
if grep -q "asset_id: $ASSET_ID" "$FLEET_FILE"; then
    echo -e "${RED}Error: Asset $ASSET_ID already exists in fleet.yaml${NC}"
    exit 1
fi

echo ""
echo "Asset type:"
echo "  1) excavator"
echo "  2) loader"
echo "  3) rigid_haul_truck"
echo "  4) dump_truck"
echo "  5) motor_grader"
echo "  6) other"
read -p "Select type [1-6]: " TYPE_NUM

case $TYPE_NUM in
    1) ASSET_TYPE="excavator" ;;
    2) ASSET_TYPE="loader" ;;
    3) ASSET_TYPE="rigid_haul_truck" ;;
    4) ASSET_TYPE="dump_truck" ;;
    5) ASSET_TYPE="motor_grader" ;;
    6) read -p "Enter asset type: " ASSET_TYPE ;;
    *) echo -e "${RED}Invalid selection${NC}"; exit 1 ;;
esac

read -p "Make (e.g., CAT, Komatsu, Hitachi): " MAKE
read -p "Model (e.g., 390F, 830E-5): " MODEL
read -p "Serial number: " SERIAL
read -p "Year: " YEAR
read -p "Host to deploy on (e.g., host-01): " HOST

echo ""
echo "Specifications:"
read -p "Fuel tank capacity (liters): " TANK_CAPACITY
read -p "Average fuel consumption (L/hr): " AVG_CONSUMPTION
read -p "Current hour meter reading: " INITIAL_HOURS

echo ""
echo "Telegram configuration:"
read -p "Telegram group (e.g., @ex003_ops): " TELEGRAM_GROUP

echo ""
echo "Primary operator:"
read -p "  Name: " OP1_NAME
read -p "  Telegram handle (e.g., @john): " OP1_TG

# Generate YAML block
YAML_BLOCK=$(cat <<EOF

  - asset_id: $ASSET_ID
    type: $ASSET_TYPE
    make: $MAKE
    model: "$MODEL"
    serial: "$SERIAL"
    year: $YEAR
    host: $HOST

    specs:
      tank_capacity: $TANK_CAPACITY
      avg_consumption: $AVG_CONSUMPTION
      min_consumption: $((AVG_CONSUMPTION - 5))
      max_consumption: $((AVG_CONSUMPTION + 10))

    initial:
      hours: $INITIAL_HOURS
      lat: 0
      lon: 0

    operators:
      - name: "$OP1_NAME"
        telegram: "$OP1_TG"
        consumption_rate: $AVG_CONSUMPTION

    telegram_group: "$TELEGRAM_GROUP"
EOF
)

echo ""
echo "======================================"
echo "Asset configuration to add:"
echo "======================================"
echo "$YAML_BLOCK"
echo ""

read -p "Add this asset to fleet.yaml? [y/N]: " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Find the line number of "hosts:" section to insert before it
HOSTS_LINE=$(grep -n "^hosts:" "$FLEET_FILE" | cut -d: -f1)

if [ -z "$HOSTS_LINE" ]; then
    echo "$YAML_BLOCK" >> "$FLEET_FILE"
    echo ""
    echo -e "${YELLOW}Warning: Could not find 'hosts:' section in fleet.yaml${NC}"
    echo -e "${YELLOW}Asset was appended to end of file - please verify placement${NC}"
    echo -e "${GREEN}Asset $ASSET_ID added to fleet.yaml${NC}"
else
    # Insert the new asset before the hosts section using temp file
    TEMP_FILE="${FLEET_FILE}.tmp"
    head -n $((HOSTS_LINE - 1)) "$FLEET_FILE" > "$TEMP_FILE"
    echo "$YAML_BLOCK" >> "$TEMP_FILE"
    echo "" >> "$TEMP_FILE"
    tail -n +$HOSTS_LINE "$FLEET_FILE" >> "$TEMP_FILE"
    mv "$TEMP_FILE" "$FLEET_FILE"
    echo ""
    echo -e "${GREEN}Asset $ASSET_ID added to fleet.yaml (inserted before hosts section)${NC}"
fi

echo ""
echo "Next steps:"
echo "  1. Verify asset is in the 'assets:' section (before 'hosts:')"
echo "  2. Add TELEGRAM_TOKEN_${ASSET_ID//-/_} to .env"
echo "  3. Run: python scripts/generate-configs.py"
echo "  4. Deploy the new asset container"
