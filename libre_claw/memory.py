"""Memory integration for Libre Claw.

HTTP client for ChromaDB at stargate.local:8420
"""

from typing import Any, Dict, List, Optional

import httpx


class MemoryClient:
    """HTTP client for ChromaDB memory server.

    Provides semantic search and storage for long-term memory.
    """

    def __init__(
        self,
        url: str = "http://stargate.local:8420",
        collection_name: str = "libre_claw_memories",
    ):
        """Initialize memory client.

        Args:
            url: ChromaDB server URL
            collection_name: Default collection name
        """
        self.url = url.rstrip("/")
        self.collection_name = collection_name
        self._client = httpx.Client(timeout=30.0)

    def is_available(self) -> bool:
        """Check if memory server is available.

        Returns:
            True if server is responding
        """
        try:
            response = self._client.get(f"{self.url}/health")
            return response.status_code == 200
        except Exception:
            return False

    def search(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        collection: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search memories by semantic similarity.

        Args:
            query: Search query
            n_results: Number of results to return
            where: Optional metadata filter
            collection: Optional collection name (defaults to self.collection_name)

        Returns:
            List of matching memories with metadata
        """
        collection = collection or self.collection_name

        payload = {
            "collection_name": collection,
            "query_texts": [query],
            "n_results": n_results,
        }

        if where:
            payload["where"] = where

        try:
            response = self._client.post(
                f"{self.url}/query",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            # Format results
            results = []
            if "results" in data:
                for i, doc in enumerate(data["results"].get("documents", [[]])[0]):
                    result = {
                        "id": data["results"].get("ids", [[""] * n_results])[0][i],
                        "document": doc,
                        "distance": data["results"].get("distances", [[]])[0][i],
                        "metadata": data["results"].get("metadatas", [{}])[0][i],
                    }
                    results.append(result)

            return results

        except httpx.HTTPStatusError as e:
            print(f"Memory search HTTP error: {e}")
            return []
        except Exception as e:
            print(f"Memory search error: {e}")
            return []

    def add(
        self,
        document: str,
        metadata: Optional[Dict[str, Any]] = None,
        id: Optional[str] = None,
        collection: Optional[str] = None,
    ) -> Optional[str]:
        """Add a memory to the collection.

        Args:
            document: Text content to store
            metadata: Optional metadata
            id: Optional custom ID
            collection: Optional collection name

        Returns:
            Memory ID or None if failed
        """
        collection = collection or self.collection_name

        payload = {
            "collection_name": collection,
            "documents": [document],
        }

        if metadata:
            payload["metadatas"] = [metadata]
        if id:
            payload["ids"] = [id]

        try:
            response = self._client.post(
                f"{self.url}/add",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("ids", [None])[0]

        except Exception as e:
            print(f"Memory add error: {e}")
            return None

    def delete(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        collection: Optional[str] = None,
    ) -> bool:
        """Delete memories from collection.

        Args:
            ids: List of memory IDs to delete
            where: Optional metadata filter for deletion
            collection: Optional collection name

        Returns:
            True if successful
        """
        collection = collection or self.collection_name

        payload = {
            "collection_name": collection,
        }

        if ids:
            payload["ids"] = ids
        if where:
            payload["where"] = where

        try:
            response = self._client.post(
                f"{self.url}/delete",
                json=payload,
            )
            response.raise_for_status()
            return True

        except Exception as e:
            print(f"Memory delete error: {e}")
            return False

    def get_collection_info(self, collection: Optional[str] = None) -> Dict[str, Any]:
        """Get information about a collection.

        Args:
            collection: Optional collection name

        Returns:
            Collection info dictionary
        """
        collection = collection or self.collection_name

        try:
            response = self._client.get(
                f"{self.url}/collection/{collection}",
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            print(f"Collection info error: {e}")
            return {}

    def list_collections(self) -> List[str]:
        """List all available collections.

        Returns:
            List of collection names
        """
        try:
            response = self._client.get(f"{self.url}/collections")
            response.raise_for_status()
            data = response.json()
            return data.get("collections", [])

        except Exception as e:
            print(f"List collections error: {e}")
            return []

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __del__(self) -> None:
        """Cleanup on deletion."""
        try:
            self.close()
        except Exception:
            pass


class MemoryManager:
    """High-level memory management with caching."""

    def __init__(
        self,
        url: str = "http://stargate.local:8420",
        collection_name: str = "libre_claw_memories",
    ):
        """Initialize memory manager.

        Args:
            url: ChromaDB server URL
            collection_name: Default collection name
        """
        self.client = MemoryClient(url, collection_name)

    def remember(
        self,
        content: str,
        memory_type: str = "general",
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """Store a memory with metadata.

        Args:
            content: Memory content
            memory_type: Type (milestone, conversation, preference, etc.)
            importance: Importance score 0-1
            tags: Optional tags

        Returns:
            True if successful
        """
        metadata = {
            "type": memory_type,
            "importance": importance,
            "timestamp": str(datetime.now().isoformat()),
        }

        if tags:
            metadata["tags"] = ",".join(tags)

        result = self.client.add(document=content, metadata=metadata)
        return result is not None

    def recall(
        self,
        query: str,
        memory_type: Optional[str] = None,
        min_importance: float = 0.0,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Recall memories matching query.

        Args:
            query: Search query
            memory_type: Optional type filter
            min_importance: Minimum importance score
            limit: Maximum results

        Returns:
            List of matching memories
        """
        where = {}
        if memory_type:
            where["type"] = memory_type
        if min_importance > 0:
            where["importance"] = {"$gte": min_importance}

        results = self.client.search(
            query=query,
            n_results=limit,
            where=where if where else None,
        )

        return results


