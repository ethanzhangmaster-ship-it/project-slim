"""CAF — Character-as-Feature layer.

Parallel data stream:
  Image + Metadata + Metrics → CAF Extractor → Feature Attribution → Updater → character_schema.json

Does NOT alter V1 main pipeline.
"""
