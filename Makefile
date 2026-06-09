# fake-payment-gateway -- developer task runner. Thin wrappers around uv + docker so
# common workflows are one keystroke. All targets are .PHONY: nothing
# produces a file at the project root.

REPO_NAME := fake-payment-gateway

# OWNER / VERSION are used to compute the docker image tag.
# Defaults match what versions.yml in place-order-integration expects
# for local builds, so `make image` here produces a tag the integrator
# will pick up unchanged.
OWNER   ?= local
VERSION ?= 0.1.0
IMAGE   := ghcr.io/$(OWNER)/$(REPO_NAME):$(VERSION)

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z][a-zA-Z0-9_-]*:.*?## / {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# --- Dependencies ----------------------------------------------------------

.PHONY: sync
sync: ## Resolve and install dependencies (incl. dev)
	uv sync

# --- Quality gates ---------------------------------------------------------

.PHONY: lint
lint: ## Run ruff in check mode
	uv run ruff check .

.PHONY: fmt
fmt: ## Autoformat with ruff format
	uv run ruff format .

.PHONY: fix
fix: ## Apply autofixable ruff findings
	uv run ruff check . --fix

.PHONY: check
check: ## Static type-check (mypy strict)
	uv run mypy src tests

# --- Tests -----------------------------------------------------------------

.PHONY: test
test: ## Run pytest
	uv run pytest

# --- Packaging -------------------------------------------------------------

.PHONY: version
version: ## Print the VERSION that would be stamped into the image
	@echo $(VERSION)

.PHONY: image
image: ## Build the docker image as $(IMAGE)
	docker build --build-arg VERSION=$(VERSION) -t $(IMAGE) .

.PHONY: image-size
image-size: ## Show built image size
	@docker images --format '{{.Repository}}:{{.Tag}}\t{{.Size}}' \
	  | awk -v t='$(IMAGE)' '$$1==t {print; found=1} END {if (!found) print "image $(IMAGE) not built"}'

# --- Cleanup ---------------------------------------------------------------

.PHONY: clean-image
clean-image: ## Remove the locally-built image from the Docker daemon
	@docker rmi $(IMAGE) 2>/dev/null && echo "removed $(IMAGE)" || echo "image $(IMAGE) not present"

.PHONY: clean
clean: ## Remove image + .venv + tool caches
	rm -rf .venv .ruff_cache .mypy_cache .pytest_cache
	@docker rmi $(IMAGE) 2>/dev/null || true

# --- Composite -------------------------------------------------------------

.PHONY: ci
ci: lint check test ## What CI runs: lint + type-check + tests
