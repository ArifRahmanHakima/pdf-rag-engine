"""
Cleanup service - handles document and session deletion with VDB cleanup
"""

import json
import shutil
from pathlib import Path


async def delete_document_service(
    session_id: str,
    doc_id: str,
    sessions_dir: Path,
    working_dir: Path,
    session_status: dict
):
    """
    Delete a document and ALL its associated data (file, chunks, embeddings, vectors)
    
    Args:
        session_id: Session identifier
        doc_id: Document identifier
        sessions_dir: Sessions directory path
        working_dir: Working directory path
        session_status: Session status dictionary (to update)
    """
    try:
        session_dir = sessions_dir / session_id
        doc_dir = session_dir / "documents" / doc_id
        
        print(f"\n[*] Deleting document: {doc_id} from session {session_id}")
        
        # ===== 1. DELETE from LightRAG stores =====
        try:
            chunks_file = Path(working_dir) / "kv_store_text_chunks.json"
            if chunks_file.exists():
                with open(chunks_file, 'r', encoding='utf-8', errors='ignore') as f:
                    chunks_data = json.load(f)
                
                # Get doc_id from documents.json
                session_dir = sessions_dir / session_id
                doc_metadata_file = session_dir / "documents.json"
                doc_full_id = None
                
                if doc_metadata_file.exists():
                    with open(doc_metadata_file, 'r', encoding='utf-8', errors='ignore') as f:
                        docs_meta = json.load(f)
                        if doc_id in docs_meta:
                            doc_full_id = docs_meta[doc_id].get('full_doc_id', None)
                
                # Filter chunks
                doc_id_marker = f"[DOC_ID:{doc_id}]"
                chunks_to_keep = {}
                deleted_count = 0
                
                for chunk_id, chunk_content in chunks_data.items():
                    should_delete = False
                    
                    if isinstance(chunk_content, dict):
                        # Check marker in content
                        if 'content' in chunk_content:
                            content = chunk_content['content']
                            if doc_id_marker in content:
                                should_delete = True
                        
                        # Check full_doc_id field
                        chunk_full_id = chunk_content.get('full_doc_id', None)
                        if chunk_full_id and doc_full_id and chunk_full_id == doc_full_id:
                            should_delete = True
                    
                    if not should_delete:
                        chunks_to_keep[chunk_id] = chunk_content
                    else:
                        deleted_count += 1
                
                # Write back filtered chunks
                with open(chunks_file, 'w', encoding='utf-8') as f:
                    json.dump(chunks_to_keep, f, ensure_ascii=False, indent=2)
                
                print(f"    [✓] Deleted {deleted_count} chunks from global store")
        except Exception as e:
            print(f"    [!] Error cleaning chunks store: {e}")
        
        # Clean up VDB files
        try:
            vdb_files = [
                Path(working_dir) / "vdb_chunks.json",
                Path(working_dir) / "vdb_entities.json",
                Path(working_dir) / "vdb_relationships.json"
            ]
            
            doc_id_marker = f"[DOC_ID:{doc_id}]"
            
            for vdb_file in vdb_files:
                if not vdb_file.exists():
                    continue
                    
                try:
                    with open(vdb_file, 'r', encoding='utf-8', errors='ignore') as f:
                        vdb_data = json.load(f)
                    
                    # Filter out entries related to this document
                    if isinstance(vdb_data, dict):
                        filtered_data = {}
                        deleted = 0
                        
                        for key, value in vdb_data.items():
                            # Check if entry contains doc_id_marker
                            entry_str = json.dumps(value)
                            if doc_id_marker not in entry_str:
                                filtered_data[key] = value
                            else:
                                deleted += 1
                        
                        if deleted > 0:
                            with open(vdb_file, 'w', encoding='utf-8') as f:
                                json.dump(filtered_data, f, ensure_ascii=False, indent=2)
                            print(f"    [✓] Cleaned {vdb_file.name} (removed {deleted} entries)")
                except Exception as e:
                    print(f"    [!] Error cleaning {vdb_file.name}: {e}")
        except Exception as e:
            print(f"    [!] Error in VDB cleanup: {e}")
        
        # ===== 2. DELETE document directory =====
        if doc_dir.exists():
            shutil.rmtree(doc_dir, ignore_errors=True)
            print(f"    [✓] Deleted document directory")
        
        # ===== 3. UPDATE documents.json =====
        docs_file = session_dir / "documents.json"
        docs = {}
        if docs_file.exists():
            with open(docs_file, 'r', encoding='utf-8', errors='ignore') as f:
                docs = json.load(f)
            
            if doc_id in docs:
                del docs[doc_id]
                with open(docs_file, 'w', encoding='utf-8') as f:
                    json.dump(docs, f, ensure_ascii=False, indent=2)
                print(f"    [✓] Removed from documents.json")
        
        # ===== 4. UPDATE session status =====
        if session_id in session_status:
            if session_status[session_id].get("selected_doc") == doc_id:
                # Find another document to select
                remaining_docs = list(docs.keys())
                if remaining_docs:
                    session_status[session_id]["selected_doc"] = remaining_docs[0]
                else:
                    session_status[session_id]["selected_doc"] = None
        
        # ===== 5. DELETE entire session if empty =====
        if len(docs) == 0:
            if session_dir.exists():
                shutil.rmtree(session_dir, ignore_errors=True)
                print(f"    [✓] Session folder deleted (no documents remaining)")
            
            # Remove from session_status
            if session_id in session_status:
                del session_status[session_id]
        
        print(f"[✓] Fully deleted document: {doc_id} (file + chunks + embeddings)\n")
        return True
    
    except Exception as e:
        print(f"[!] Delete error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def delete_session_service(session_id: str, sessions_dir: Path, working_dir: Path, session_status: dict):
    """
    Delete entire session with VDB cleanup
    
    Args:
        session_id: Session identifier
        sessions_dir: Sessions directory path
        working_dir: Working directory path
        session_status: Session status dictionary (to update)
    """
    try:
        session_dir = sessions_dir / session_id
        
        if session_id in session_status:
            del session_status[session_id]
        
        if session_dir.exists():
            shutil.rmtree(session_dir)
        
        # Clean up VDB files
        try:
            vdb_files = [
                Path(working_dir) / "vdb_chunks.json",
                Path(working_dir) / "vdb_entities.json",
                Path(working_dir) / "vdb_relationships.json"
            ]
            
            for vdb_file in vdb_files:
                if vdb_file.exists():
                    vdb_file.unlink()
                    print(f"[✓] Deleted {vdb_file.name}")
            
            print(f"[✓] Session {session_id} deleted with full VDB cleanup")
        except Exception as e:
            print(f"[!] Warning: Could not clean VDB files: {e}")
        
        return True
    
    except Exception as e:
        print(f"[!] Delete session error: {e}")
        return False
