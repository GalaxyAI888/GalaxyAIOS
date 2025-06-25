import multiprocessing
from .core import AIGCProcessor

def start_processor(task_type: str, account_id: str):
    """安全启动独立进程"""
    def _run():
        try:
            processor = AIGCProcessor(account_id)
            processor.run(task_type)
        except Exception as e:
            print(f"处理器崩溃: {e}")
            raise

    p = multiprocessing.Process(
        target=_run,
        daemon=True,
        name=f"AIGC-{task_type}-{account_id}"
    )
    p.start()
    return p
