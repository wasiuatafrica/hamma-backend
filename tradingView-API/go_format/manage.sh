#!/bin/bash

# Unified Price System Management Script

BINARY_NAME="unified_price_system"
LOG_FILE="system.log"
PID_FILE="system.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

function build() {
    echo -e "${YELLOW}Building $BINARY_NAME...${NC}"
    go build -o $BINARY_NAME unified_price_system.go
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Build successful!${NC}"
    else
        echo -e "${RED}Build failed!${NC}"
        exit 1
    fi
}

function start() {
    if [ -f $PID_FILE ]; then
        PID=$(cat $PID_FILE)
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${YELLOW}$BINARY_NAME is already running (PID: $PID)${NC}"
            return
        else
            echo -e "${YELLOW}Removing stale PID file${NC}"
            rm $PID_FILE
        fi
    fi

    # Check if MONGO_URL is set
    if [ -z "$MONGO_URL" ]; then
        echo -e "${RED}Error: MONGO_URL environment variable is not set${NC}"
        echo "Please set it with: export MONGO_URL=\"your_mongodb_connection_string\""
        exit 1
    fi

    echo -e "${YELLOW}Starting $BINARY_NAME in background...${NC}"
    nohup ./$BINARY_NAME > $LOG_FILE 2>&1 &
    PID=$!
    echo $PID > $PID_FILE
    echo -e "${GREEN}$BINARY_NAME started with PID: $PID${NC}"
    echo -e "${GREEN}Logs are being written to: $LOG_FILE${NC}"
}

function stop() {
    if [ ! -f $PID_FILE ]; then
        echo -e "${YELLOW}$BINARY_NAME is not running (no PID file found)${NC}"
        return
    fi

    PID=$(cat $PID_FILE)
    if ps -p $PID > /dev/null 2>&1; then
        echo -e "${YELLOW}Stopping $BINARY_NAME (PID: $PID)...${NC}"
        kill $PID
        sleep 2
        
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${RED}Process still running, force killing...${NC}"
            kill -9 $PID
        fi
        
        rm $PID_FILE
        echo -e "${GREEN}$BINARY_NAME stopped${NC}"
    else
        echo -e "${YELLOW}$BINARY_NAME is not running${NC}"
        rm $PID_FILE
    fi
}

function status() {
    if [ -f $PID_FILE ]; then
        PID=$(cat $PID_FILE)
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${GREEN}$BINARY_NAME is running (PID: $PID)${NC}"
            echo -e "${GREEN}Started: $(ps -o lstart= -p $PID)${NC}"
            echo -e "${GREEN}Memory usage: $(ps -o rss= -p $PID | awk '{print $1/1024" MB"}')${NC}"
        else
            echo -e "${RED}$BINARY_NAME is not running (stale PID file)${NC}"
            rm $PID_FILE
        fi
    else
        echo -e "${RED}$BINARY_NAME is not running${NC}"
    fi
}

function logs() {
    if [ ! -f $LOG_FILE ]; then
        echo -e "${RED}Log file $LOG_FILE not found${NC}"
        return
    fi
    
    if [ "$1" = "-f" ] || [ "$1" = "--follow" ]; then
        echo -e "${YELLOW}Following logs (Ctrl+C to stop)...${NC}"
        tail -f $LOG_FILE
    else
        echo -e "${YELLOW}Last 50 lines of logs:${NC}"
        tail -50 $LOG_FILE
    fi
}

function restart() {
    echo -e "${YELLOW}Restarting $BINARY_NAME...${NC}"
    stop
    sleep 1
    start
}

function help() {
    echo "Usage: $0 {build|start|stop|restart|status|logs}"
    echo ""
    echo "Commands:"
    echo "  build     - Build the Go binary"
    echo "  start     - Start the service in background"
    echo "  stop      - Stop the service"
    echo "  restart   - Restart the service"
    echo "  status    - Show service status"
    echo "  logs      - Show recent logs"
    echo "  logs -f   - Follow logs in real-time"
    echo ""
    echo "Before starting, make sure to set the MONGO_URL environment variable:"
    echo "  export MONGO_URL=\"your_mongodb_connection_string\""
}

# Main script logic
case "$1" in
    build)
        build
        ;;
    start)
        if [ ! -f $BINARY_NAME ]; then
            echo -e "${YELLOW}Binary not found, building first...${NC}"
            build
        fi
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs $2
        ;;
    *)
        help
        exit 1
        ;;
esac
