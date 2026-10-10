# RAG Backend

This backend uses FastAPI, Qdrant, OpenAI embeddings, and `gpt-4o-mini`.

## Flow

1. Convert source files to Markdown.
2. Chunk Markdown into smaller Markdown files and `outputs/chunks/chunks.jsonl`.
3. Embed each chunk with OpenAI embeddings.
4. Store vectors and metadata in Qdrant.
5. Retrieve relevant chunks for a question.
6. Ask `gpt-4o-mini` to answer using only those chunks.

## Commands

```bash
python3 scripts/chunk_markdown.py \
  --input-dir outputs/markdown \
  --markdown-output-dir outputs/markdown_chunked \
  --chunks-output outputs/chunks/chunks.jsonl \
  --max-chars 7000
```

```bash
docker compose -f docker-compose.qdrant.yml up -d
```

```bash
python3 scripts/ingest_qdrant.py \
  --chunks-path outputs/chunks/chunks.jsonl \
  --batch-size 32
```

```bash
uvicorn app:app --reload --port 8000
```

## API

- `GET /health`
- `POST /search`
- `POST /chat`

Example:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"What are common G60 US complaints?","top_k":8,"filters":{"vehicle_model":"G60","market":"US"}}'
```
