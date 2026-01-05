#!/usr/bin/env python
"""Clear all vectors from Qdrant"""

from qdrant_client import QdrantClient
from qdrant_client.http import models

client = QdrantClient(url="http://localhost:6333")

try:
    # Get all collections
    collections = client.get_collections()
    
    for collection in collections.collections:
        collection_name = collection.name
        print(f"[*] Clearing collection: {collection_name}")
        
        # Get all points
        points = client.scroll(collection_name, limit=10000)
        point_ids = [point.id for point in points[0]]
        
        if point_ids:
            # Delete all points
            client.delete(
                collection_name,
                points_selector=models.PointIdsList(
                    points=point_ids
                )
            )
            print(f"  [✓] Deleted {len(point_ids)} vectors")
        else:
            print(f"  [✓] Collection already empty")
    
    print("[✓] Qdrant vectors cleared successfully!")
    
except Exception as e:
    print(f"[!] Error: {e}")
    import traceback
    traceback.print_exc()
