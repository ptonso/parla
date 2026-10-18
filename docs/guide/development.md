# Development

```bash
pip install -e ".[dev,svg,pdf]"
pytest -m "not docker"
ruff check src tests
mypy src
```

Tests marked `docker` build through the real container and skip until `parla image build` has built the image. The design is in [specs/](../../specs/README.md).
