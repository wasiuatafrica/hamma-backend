FROM golang:1.21-alpine AS builder

# Set working directory
WORKDIR /app

# Install dependencies
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o unified_price_system unified_price_system.go

# Final stage
FROM alpine:latest

# Install ca-certificates and timezone data
RUN apk --no-cache add ca-certificates tzdata

# Create app directory
WORKDIR /app

# Copy binary from builder stage
COPY --from=builder /app/unified_price_system .

# Create directories for logs and cache
RUN mkdir -p logs cache

# Set timezone to Lagos
ENV TZ=Africa/Lagos

# Expose port (if you add HTTP endpoints later)
EXPOSE 8080

# Run the binary
CMD ["./unified_price_system"]
