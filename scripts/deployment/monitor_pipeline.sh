#!/bin/bash
# Monitor all pipeline services for the latest post
# Usage: bash /tmp/monitor_pipeline.sh [post_title]

SERVICES="media_preprocessor image_tagger scene_recognition image_captioning image_embedding content_moderation kaleidoscope-backend post_aggregator es_sync dlq_processor"

echo "=== PIPELINE MONITOR - $(date -u) ==="
echo "Showing last 30 lines from each service..."
echo ""

for svc in $SERVICES; do
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  SERVICE: $svc"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  docker logs --tail=30 "$svc" 2>&1 | grep -v "^$" || echo "  [no logs or container not found]"
  echo ""
done
