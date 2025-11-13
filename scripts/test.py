import os
import time
from pathlib import Path

# ====== 用户可改的输入文件名 ======
SRC_PATH = Path("TEST1_0001_adc1.bin")

# ====== 自动生成的目标文件名 ======
DST_PATH = SRC_PATH.with_suffix(SRC_PATH.suffix + ".copy.bin")

# ====== 分块大小（仅在启用分块读写时生效）======
CHUNK_SIZE = 16 * 1024 * 1024  # 16 MB

def human(n_bytes: int) -> str:
    # 简单的人类可读大小
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n_bytes < 1024.0:
            return f"{n_bytes:.2f} {unit}"
        n_bytes /= 1024.0
    return f"{n_bytes:.2f} PB"

def measure_copy_readall(src: Path, dst: Path):
    """
    方案A：一次性读入内存 -> 再一次性写出
    """
    if not src.exists():
        raise FileNotFoundError(f"源文件不存在：{src}")

    size = src.stat().st_size

    # 读
    t0 = time.perf_counter()
    with open(src, "rb") as f:
        data = f.read()
    t1 = time.perf_counter()

    # 写
    with open(dst, "wb") as f:
        f.write(data)
    t2 = time.perf_counter()

    read_s  = t1 - t0
    write_s = t2 - t1

    read_mbs  = (size / (1024 * 1024)) / read_s if read_s > 0 else float("inf")
    write_mbs = (size / (1024 * 1024)) / write_s if write_s > 0 else float("inf")

    return {
        "method": "readall",
        "size": size,
        "read_time_s": read_s,
        "write_time_s": write_s,
        "read_MBps": read_mbs,
        "write_MBps": write_mbs,
    }

def measure_copy_chunked(src: Path, dst: Path, chunk_size: int = CHUNK_SIZE):
    """
    方案B：分块流式读写（更省内存，适合超大文件）
    """
    if not src.exists():
        raise FileNotFoundError(f"源文件不存在：{src}")

    size = src.stat().st_size
    read_bytes = 0
    write_bytes = 0

    t0 = time.perf_counter()
    with open(src, "rb") as fin:
        with open(dst, "wb") as fout:
            # 单独计时读取与写入
            read_time = 0.0
            write_time = 0.0

            while True:
                t_r0 = time.perf_counter()
                chunk = fin.read(chunk_size)
                t_r1 = time.perf_counter()
                read_time += (t_r1 - t_r0)

                if not chunk:
                    break
                read_bytes += len(chunk)

                t_w0 = time.perf_counter()
                fout.write(chunk)
                t_w1 = time.perf_counter()
                write_time += (t_w1 - t_w0)
                write_bytes += len(chunk)
    t1 = time.perf_counter()

    read_mbs  = (read_bytes / (1024 * 1024)) / read_time if read_time > 0 else float("inf")
    write_mbs = (write_bytes / (1024 * 1024)) / write_time if write_time > 0 else float("inf")

    return {
        "method": "chunked",
        "size": size,
        "read_time_s": read_time,
        "write_time_s": write_time,
        "total_elapsed_s": (t1 - t0),
        "read_MBps": read_mbs,
        "write_MBps": write_mbs,
    }

def main():
    print(f"源文件：{SRC_PATH.resolve()}")
    # 默认：一次性读 -> 写
    res = measure_copy_readall(SRC_PATH, DST_PATH)
    print("\n=== 一次性读写（readall） ===")
    print(f"文件大小      : {human(res['size'])}")
    print(f"读取耗时      : {res['read_time_s']:.6f} s   ({res['read_MBps']:.2f} MB/s)")
    print(f"写入耗时      : {res['write_time_s']:.6f} s   ({res['write_MBps']:.2f} MB/s)")
    print(f"拷贝到       : {DST_PATH.resolve()}")

    # 如需对比分块法，取消下面三行的注释：
    # res2 = measure_copy_chunked(SRC_PATH, DST_PATH.with_suffix(DST_PATH.suffix + ".chunked"))
    # print("\n=== 分块读写（chunked） ===")
    # print(res2)

    # 删除新文件
    try:
        os.remove(DST_PATH)
        print(f"\n已删除拷贝文件：{DST_PATH}")
    except Exception as e:
        print(f"\n删除新文件失败：{e}")

if __name__ == "__main__":
    main()