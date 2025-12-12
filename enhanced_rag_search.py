"""
Enhanced RAG module with diagnostics, query expansion, and confidence checking
"""
import json
import os
from typing import List, Dict, Tuple
import numpy as np
from embedding_qwen import get_embedding_func

class EnhancedRAGSearch:
    def __init__(self, working_dir: str, top_k: int = 8):
        """Initialize enhanced search with diagnostics"""
        self.working_dir = working_dir
        self.top_k = top_k
        self.embedding_func = get_embedding_func()
        self._load_chunks()
    
    def _load_chunks(self):
        """Load chunks and embeddings from storage"""
        try:
            chunks_path = f"{self.working_dir}/kv_store_text_chunks.json"
            if not os.path.exists(chunks_path):
                print(f"[!] Chunks file not found: {chunks_path}")
                self.chunks = []
                self.embeddings = []
                self.chunk_sources = []
                return
            
            with open(chunks_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.chunks = []
                self.embeddings = []
                self.chunk_sources = []
                
                # LightRAG structure: {chunk_id: {content, metadata, ...}}
                for chunk_id, chunk_data in data.items():
                    if isinstance(chunk_data, dict) and 'content' in chunk_data:
                        self.chunks.append(chunk_data['content'])
                        self.chunk_sources.append({
                            'chunk_id': chunk_id,
                            'doc_id': chunk_data.get('full_doc_id', ''),
                            'metadata': {
                                'tokens': chunk_data.get('tokens', 0),
                                'chunk_order': chunk_data.get('chunk_order_index', 0),
                                'file_path': chunk_data.get('file_path', '')
                            }
                        })
                
                if self.chunks:
                    print(f"[✓] Loaded {len(self.chunks)} chunks from storage")
                else:
                    print(f"[!] No chunks found in storage (file empty)")
        except Exception as e:
            print(f"[!] Error loading chunks: {e}")
            self.chunks = []
            self.embeddings = []
            self.chunk_sources = []
    
    def reload_chunks(self):
        """Reload chunks after new ingestion - call this after adding documents"""
        print("[*] Reloading chunks from storage...")
        self._load_chunks()
    
    def _get_query_variations(self, query: str) -> List[str]:
        """
        Generate query variations for better matching
        
        Examples:
        - Original: "apa isi point a bagian menimbang"
        - Variations: 
          - "point a menimbang"
          - "huruf a menimbang"
          - "isi poin a bagian menimbang"
        """
        variations = [query]  # Original query
        
        # Replace aliases
        replacements = {
            'point': ['poin', 'huruf'],
            'poin': ['point', 'huruf'],
            'huruf': ['point', 'poin'],
            'bagian': ['bab', 'pasal'],
            'isi': ['konten', 'berisi'],
        }
        
        for original, alternatives in replacements.items():
            if original in query.lower():
                for alt in alternatives:
                    new_query = query.lower().replace(original, alt)
                    if new_query not in variations:
                        variations.append(new_query)
        
        return variations[:3]  # Return top 3 variations
    
    def search_with_diagnostics(self, query: str, return_scores: bool = False) -> Tuple[List[Dict], Dict]:
        """
        Search with detailed diagnostics
        
        Returns:
        - chunks: List of retrieved chunks with metadata
        - diagnostics: Search diagnostics (query variations, scores, etc)
        """
        if not self.chunks:
            return [], {"error": "No chunks loaded"}
        
        diagnostics = {
            "original_query": query,
            "query_variations": self._get_query_variations(query),
            "retrieved_chunks": [],
            "scores": []
        }
        
        # Generate embeddings for all query variations
        all_results = []
        
        for var_query in diagnostics["query_variations"]:
            try:
                query_embedding = self.embedding_func(var_query)
                query_vec = np.array(query_embedding).reshape(1, -1)
                
                # Compute similarity for all chunks
                similarities = []
                for chunk in self.chunks:
                    chunk_embedding = self.embedding_func(chunk)
                    chunk_vec = np.array(chunk_embedding).reshape(1, -1)
                    
                    # Cosine similarity
                    similarity = np.dot(query_vec, chunk_vec.T)[0][0] / (
                        np.linalg.norm(query_vec) * np.linalg.norm(chunk_vec) + 1e-10
                    )
                    similarities.append(float(similarity))
                
                # Get top-k
                top_indices = np.argsort(similarities)[-self.top_k:][::-1]
                
                for idx in top_indices:
                    all_results.append({
                        'index': idx,
                        'chunk': self.chunks[idx],
                        'score': similarities[idx],
                        'source': self.chunk_sources[idx],
                        'query_var': var_query
                    })
            except Exception as e:
                print(f"[!] Error processing query variation: {e}")
                continue
        
        # Deduplicate and sort by score
        seen_chunks = set()
        final_results = []
        for result in sorted(all_results, key=lambda x: x['score'], reverse=True):
            chunk_hash = hash(result['chunk'])
            if chunk_hash not in seen_chunks:
                seen_chunks.add(chunk_hash)
                final_results.append(result)
                
                if len(final_results) >= self.top_k:
                    break
        
        # Prepare output
        chunks_output = [
            {
                'content': r['chunk'],
                'score': r['score'],
                'source': r['source'],
                'query_variation': r['query_var']
            }
            for r in final_results
        ]
        
        diagnostics["retrieved_chunks"] = [
            {
                'index': i,
                'score': r['score'],
                'source': r['source'],
                'preview': r['chunk'][:200] + '...' if len(r['chunk']) > 200 else r['chunk']
            }
            for i, r in enumerate(final_results)
        ]
        
        return chunks_output, diagnostics
    
    def check_answer_confidence(self, answer: str, chunks: List[Dict], threshold: float = 0.6) -> Dict:
        """
        Check if answer is confident (based on chunks content)
        
        Returns confidence assessment:
        - high: Answer likely supported by chunks
        - medium: Answer partially in chunks
        - low: Answer might be hallucinated
        """
        if not chunks:
            return {"confidence": "low", "reason": "No supporting chunks found"}
        
        # Extract key phrases from answer (simple approach)
        answer_lower = answer.lower()
        chunks_combined = " ".join([c['content'].lower() for c in chunks])
        
        # Check overlap
        overlap_score = sum(
            1 for word in answer_lower.split() 
            if len(word) > 3 and word in chunks_combined
        ) / max(len([w for w in answer_lower.split() if len(w) > 3]), 1)
        
        # Hallucination indicators
        hallucination_phrases = [
            "mungkin", "kemungkinan", "sepertinya", "diperkirakan",
            "typically", "usually", "generally", "likely"
        ]
        has_uncertainty = any(phrase in answer_lower for phrase in hallucination_phrases)
        
        # Determine confidence
        if overlap_score >= threshold and not has_uncertainty:
            confidence = "high"
            reason = f"Strong match with chunks (overlap: {overlap_score:.1%})"
        elif overlap_score >= 0.4:
            confidence = "medium"
            reason = f"Partial match with chunks (overlap: {overlap_score:.1%})"
        else:
            confidence = "low"
            reason = f"Weak match with chunks (overlap: {overlap_score:.1%}) - possible hallucination"
        
        return {
            "confidence": confidence,
            "overlap_score": overlap_score,
            "reason": reason,
            "has_uncertainty_markers": has_uncertainty
        }

# Test/Demo function
if __name__ == "__main__":
    from embedding_qwen import load_embedding_model
    
    print("[*] Loading embedding model...")
    load_embedding_model()
    
    print("[*] Initializing enhanced RAG search...")
    search = EnhancedRAGSearch(working_dir="./rag_storage", top_k=8)
    
    # Test queries
    test_queries = [
        "apa isi point a bagian menimbang",
        "poin d bagian menimbang apa",
        "apa isi point e menimbang"
    ]
    
    for query in test_queries:
        print(f"\n{'='*70}")
        print(f"Query: {query}")
        print(f"{'='*70}")
        
        chunks, diag = search.search_with_diagnostics(query)
        
        print(f"\n[Diagnostics]")
        print(f"Query variations: {diag['query_variations']}")
        print(f"Retrieved chunks: {len(diag['retrieved_chunks'])}")
        print(f"\nTop chunks:")
        for i, chunk_info in enumerate(diag['retrieved_chunks'][:3], 1):
            print(f"\n  {i}. [Score: {chunk_info['score']:.3f}] [Doc: {chunk_info['source']['doc_id']}]")
            print(f"     {chunk_info['preview']}")
