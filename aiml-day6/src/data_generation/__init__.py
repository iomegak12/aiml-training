"""Helper package for generating the synthetic RAG teaching corpus.

The package is split into small, single-purpose modules:

- ``config``     -- settings loaded from ``.env`` and project paths
- ``models``     -- the in-memory document model (Document, Section, blocks)
- ``catalog``    -- every fact used in the corpus (products and HR policies)
- ``builders``   -- turn catalog facts into Documents with template prose
- ``llm``        -- optional OpenAI prose enrichment, cache and guard rails
- ``rendering``  -- ReportLab PDF renderer (text only)
- ``qa``         -- deterministic golden question/answer set
- ``manifest``   -- corpus manifest writer
- ``verify``     -- corpus integrity checks
"""

__version__ = "0.1.0"
