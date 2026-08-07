VERSION ?= dev
LDFLAGS = -s -w -X main.Version=$(VERSION)
OUTPUT_DIR = dist

.PHONY: build clean

build:
	@mkdir -p $(OUTPUT_DIR)
	GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -ldflags="$(LDFLAGS)" -o $(OUTPUT_DIR)/host-agent-linux-amd64 .
	GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -ldflags="$(LDFLAGS)" -o $(OUTPUT_DIR)/host-agent-linux-arm64 .
	@echo "Built:"
	@ls -lh $(OUTPUT_DIR)/

clean:
	rm -rf $(OUTPUT_DIR)
