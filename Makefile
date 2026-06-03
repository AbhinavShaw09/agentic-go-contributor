REPO ?= spf13/cobra
ISSUE ?= 1234
IMAGE := agentic-go-contributor

.PHONY: deps run docker-build docker-run clean dashboard dashboard-deps

deps:
	poetry install

run:
	poetry run python -m agentic_go_contributor.cli \
		--repo $(REPO) \
		--issue $(ISSUE)

docker-build:
	docker build -t $(IMAGE) .

docker-run:
	mkdir -p results && docker run --rm \
		--env-file etc/.env \
		-v "$$(PWD)/results:/app/results" \
		-v "$$(PWD)/data:/app/data" \
		$(IMAGE) \
		--repo $(REPO) \
		--issue $(ISSUE)

dashboard-deps:
	cd dashboard && npm install

dashboard:
	cd dashboard && npm run dev

clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
