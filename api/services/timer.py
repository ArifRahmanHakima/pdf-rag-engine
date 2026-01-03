import time
import functools
from datetime import datetime

class ProcessTimer:
    """Timer untuk tracking proses PDF dengan output yang rapi"""
    
    def __init__(self, process_name: str):
        self.process_name = process_name
        self.steps = []
        self.start_time = None
        self.current_step = None
        self.current_step_start = None
    
    def start(self):
        """Mulai tracking proses"""
        self.start_time = time.perf_counter()
        self._print_header()
    
    def step(self, step_name: str):
        """Mulai step baru"""
        # Selesaikan step sebelumnya jika ada
        if self.current_step:
            self._end_current_step()
        
        self.current_step = step_name
        self.current_step_start = time.perf_counter()
        print(f"  ⏳ {step_name}...", end="", flush=True)
    
    def _end_current_step(self):
        """Selesaikan step saat ini"""
        if self.current_step and self.current_step_start:
            duration = time.perf_counter() - self.current_step_start
            self.steps.append({
                "name": self.current_step,
                "duration": duration
            })
            print(f" ✓ {self._format_duration(duration)}")
    
    def finish(self):
        """Selesaikan tracking dan print summary"""
        # Selesaikan step terakhir
        if self.current_step:
            self._end_current_step()
        
        total_time = time.perf_counter() - self.start_time
        self._print_summary(total_time)
        return total_time
    
    def _print_header(self):
        """Print header proses"""
        print(f"\n{'═'*60}")
        print(f"📄 {self.process_name}")
        print(f"{'═'*60}")
    
    def _print_summary(self, total_time: float):
        """Print summary timing dengan format tabel"""
        print(f"\n{'─'*60}")
        print(f"📊 TIMING BREAKDOWN")
        print(f"{'─'*60}")
        
        # Sort by duration (longest first) untuk identifikasi bottleneck
        sorted_steps = sorted(self.steps, key=lambda x: x['duration'], reverse=True)
        
        # Find max name length for alignment
        max_name_len = max(len(s['name']) for s in self.steps) if self.steps else 20
        
        for i, step in enumerate(self.steps):
            duration = step['duration']
            percentage = (duration / total_time * 100) if total_time > 0 else 0
            bar_len = int(percentage / 5)  # 20 chars max for 100%
            bar = "█" * bar_len + "░" * (20 - bar_len)
            
            # Mark slowest step with warning
            is_slowest = step == sorted_steps[0] and duration > 1
            marker = "🔴" if is_slowest else "  "
            
            print(f"{marker}{step['name']:<{max_name_len}} │ {self._format_duration(duration):>10} │ {bar} {percentage:>5.1f}%")
        
        print(f"{'─'*60}")
        print(f"{'TOTAL':<{max_name_len}} │ {self._format_duration(total_time):>10} │")
        print(f"{'═'*60}")
        
        # Identify bottleneck
        if sorted_steps and sorted_steps[0]['duration'] > 1:
            bottleneck = sorted_steps[0]
            print(f"⚠️  BOTTLENECK: {bottleneck['name']} ({self._format_duration(bottleneck['duration'])} - {bottleneck['duration']/total_time*100:.0f}% of total)")
        
        print()
    
    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format durasi dengan unit yang sesuai"""
        if seconds < 0.001:
            return f"{seconds * 1000000:.0f}μs"
        elif seconds < 1:
            return f"{seconds * 1000:.0f}ms"
        elif seconds < 60:
            return f"{seconds:.2f}s"
        else:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes}m {secs:.1f}s"


class Timer:
    """Context manager untuk timing sederhana (untuk backward compatibility)"""
    
    _logs = []
    _verbose = False  # Set to False to reduce noise
    
    def __init__(self, name: str, log_to_console: bool = None):
        self.name = name
        self.log_to_console = log_to_console if log_to_console is not None else Timer._verbose
        self.start_time = None
        self.duration = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration = time.perf_counter() - self.start_time
        Timer._logs.append({
            "name": self.name,
            "duration": self.duration,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        return False
    
    @classmethod
    def set_verbose(cls, verbose: bool):
        cls._verbose = verbose
    
    @classmethod
    def get_logs(cls):
        return cls._logs.copy()
    
    @classmethod
    def clear_logs(cls):
        cls._logs.clear()


import asyncio

