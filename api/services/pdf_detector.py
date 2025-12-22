import os
import fitz  # PyMuPDF

class PDFTypeDetector:
    """
    Mendeteksi tipe dan karakteristik PDF untuk memilih parser yang optimal
    """
    
    @staticmethod
    def analyze_pdf(file_path: str) -> dict:
        """
        Analisis PDF untuk menentukan karakteristiknya
        
        Mengembalikan:
            dict: {
                'type': 'text' | 'table' | 'image' | 'scan' | 'mixed',
                'has_text': bool,
                'has_images': bool,
                'has_tables': bool,
                'is_scanned': bool,
                'page_count': int,
                'confidence': float,
                'recommended_parser': str
            }
        """
        try:
            doc = fitz.open(file_path)
            
            total_pages = len(doc)
            sample_size = min(5, total_pages)
            
            text_chars = 0
            image_count = 0
            potential_tables = 0
            scanned_pages = 0
            
            for page_num in range(sample_size):
                page = doc[page_num]
                
                # 1. Cek konten teks
                text = page.get_text()
                text_chars += len(text.strip())
                
                # 2. Cek gambar
                image_list = page.get_images()
                image_count += len(image_list)
                
                # 3. Cek halaman hasil scan (gambar besar dengan teks minimal)
                if len(image_list) > 0 and len(text.strip()) < 100:
                    scanned_pages += 1
                
                # 4. Deteksi potensi tabel (heuristik ditingkatkan)
                # Hanya cek tabel jika ada cukup banyak teks
                if len(text.strip()) > 200:  # ← FIXED: require more text
                    drawings = page.get_drawings()
                    
                    # Tabel memiliki banyak garis terstruktur
                    if len(drawings) > 30:  # ← INCREASED threshold
                        potential_tables += 1
                    
                    # Cek pola mirip tabel (ditingkatkan)
                    # Hanya dihitung sebagai tabel jika ada beberapa indikator
                    table_indicators = 0
                    if '\t' in text:
                        table_indicators += 1
                    if text.count('|') > 10:  # ← Butuh banyak tanda pipa
                        table_indicators += 1
                    if text.count('\n') > 20 and text.count(' ') / len(text) < 0.15:  # Structured layout
                        table_indicators += 1
                    
                    if table_indicators >= 2:  # ← Butuh minimal 2 indikator
                        potential_tables += 1
            
            doc.close()
            
            # Hitung metrik
            avg_text_per_page = text_chars / sample_size
            has_text = avg_text_per_page > 200  # ← DITINGKATKAN dari 100
            has_images = image_count > 0
            has_tables = potential_tables > 0
            is_scanned = (scanned_pages / sample_size) > 0.5
            
            # Tentukan tipe PDF
            pdf_type, confidence = PDFTypeDetector._classify_type(
                has_text, has_images, has_tables, is_scanned, 
                avg_text_per_page, image_count, potential_tables
            )
            
            # Rekomendasikan parser
            recommended_parser = PDFTypeDetector._recommend_parser(
                pdf_type, is_scanned, has_tables, has_images
            )
            
            result = {
                'type': pdf_type,
                'has_text': has_text,
                'has_images': has_images,
                'has_tables': has_tables,
                'is_scanned': is_scanned,
                'page_count': total_pages,
                'confidence': confidence,
                'recommended_parser': recommended_parser,
                'metrics': {
                    'avg_text_per_page': avg_text_per_page,
                    'total_images': image_count,
                    'potential_table_pages': potential_tables,
                    'scanned_pages': scanned_pages
                }
            }
            
            return result
            
        except Exception as e:
            print(f"Error analyzing PDF: {e}")
            return {
                'type': 'unknown',
                'has_text': False,
                'has_images': False,
                'has_tables': False,
                'is_scanned': False,
                'page_count': 0,
                'confidence': 0.0,
                'recommended_parser': 'auto',
                'error': str(e)
            }
    
    @staticmethod
    def _classify_type(has_text, has_images, has_tables, is_scanned, 
                       avg_text, image_count, table_pages):
        """
        Klasifikasi tipe PDF berdasarkan karakteristik
        Mengembalikan: (type, confidence)
        """
        
        # Dokumen hasil scan (prioritas tertinggi)
        if is_scanned:
            return 'scan', 0.9
        
        # Dokumen banyak gambar
        if has_images and not has_text:
            return 'image', 0.85
        
        # Dokumen banyak tabel (kepercayaan ditingkatkan)
        if has_tables and table_pages >= 2:
            if avg_text > 500:
                return 'table', 0.85  # ← KEPERCAYAAN DITINGKATKAN
            else:
                return 'table', 0.7
        
        # Text document with some images/tables
        if has_text and avg_text > 1000:
            if has_images or has_tables:
                return 'mixed', 0.8  # ← KEPERCAYAAN DITINGKATKAN
            else:
                return 'text', 0.9
        
        # Simple text document
        if has_text and avg_text > 300:
            return 'text', 0.85  # ← KEPERCAYAAN DITINGKATKAN
        
        # Mixed or uncertain
        if has_text and (has_images or has_tables):
            return 'mixed', 0.65  # ← KEPERCAYAAN DITINGKATKAN
        
        return 'text', 0.5
    
    @staticmethod
    def _recommend_parser(pdf_type, is_scanned, has_tables, has_images):
        """
        Rekomendasikan parser berdasarkan tipe PDF
        """
        if is_scanned:
            return 'marker'  # Butuh OCR
        
        if pdf_type == 'scan':
            return 'marker'
        
        if pdf_type == 'table':
            return 'mineru'  # Terbaik untuk tabel
        
        if pdf_type == 'image':
            return 'mineru'  # Bagus untuk gambar
        
        if pdf_type == 'mixed':
            if has_tables:
                return 'mineru'
            elif has_images:
                return 'auto'
            else:
                return 'auto'
        
        if pdf_type == 'text':
            return 'pymupdf'  # Paling cepat
        
        return 'auto'
    
    @staticmethod
    def get_parser_description(parser: str) -> str:
        """Dapatkan deskripsi parser yang mudah dipahami"""
        descriptions = {
            'pymupdf': 'PyMuPDF (Cepat - teks murni)',
            'marker': 'Marker (OCR - PDF scan)',
            'mineru': 'MinerU (Lengkap - tabel & gambar)',
            'auto': 'Auto-detect (Otomatis)',
            'llama_parse': 'LlamaParse (AI-powered)',
            'unstructured': 'Unstructured (General)'
        }
        return descriptions.get(parser, parser)
    
    @staticmethod
    def print_analysis(analysis: dict):
        """Cetak hasil analisis dengan format yang rapi"""
        print("\n" + "="*60)
        print("📄 HASIL ANALISIS PDF")
        print("="*60)
        
        print(f"\n📊 Tipe: {analysis['type'].upper()} (kepercayaan: {analysis['confidence']:.0%})")
        print(f"📄 Jumlah halaman: {analysis['page_count']}")
        
        print("\n✨ Karakteristik:")
        print(f"  • Teks: {'✅' if analysis['has_text'] else '❌'}")
        print(f"  • Gambar: {'✅' if analysis['has_images'] else '❌'}")
        print(f"  • Tabel: {'✅' if analysis['has_tables'] else '❌'}")
        print(f"  • Scan: {'✅' if analysis['is_scanned'] else '❌'}")
        
        if 'metrics' in analysis:
            m = analysis['metrics']
            print("\n📈 Metrik:")
            print(f"  • Rata-rata teks/halaman: {m['avg_text_per_page']:.0f} karakter")
            print(f"  • Total gambar: {m['total_images']}")
            print(f"  • Halaman tabel: {m['potential_table_pages']}")
        
        print(f"\n🔧 Parser yang direkomendasikan: {analysis['recommended_parser']}")
        print(f"   {PDFTypeDetector.get_parser_description(analysis['recommended_parser'])}")
        print("="*60 + "\n")


 # Fungsi uji coba
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    else:
        test_file = "example.pdf"
    
    if os.path.exists(test_file):
        detector = PDFTypeDetector()
        analysis = detector.analyze_pdf(test_file)
        detector.print_analysis(analysis)
    else:
        print(f"File not found: {test_file}")
        print("Usage: python pdf_detector.py <path_to_pdf>")