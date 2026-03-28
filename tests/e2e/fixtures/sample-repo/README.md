# Sample Project

A sample project for testing documentation generation.

## Overview

This project contains a data processing pipeline with configurable steps.

## Usage

```python
from src.core import create_processor

processor = create_processor()
processor.add_step("validate")
processor.add_step("transform")
result = processor.execute({"name": "test", "type": "example"})
```
