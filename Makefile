.PHONY: preflight install test lint eval calibrate report teardown

preflight:
	bash scripts/preflight.sh

install:
	uv sync

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check src/ tests/ examples/
	uv run mypy src/

eval:
	uv run aep run --dataset rag_qa --sut examples.minimal_sut

calibrate:
	uv run aep calibrate

report:
	uv run aep report

teardown:
	bash scripts/teardown.sh
