import argparse
import asyncio
import json
import os

import aiofiles
import aiohttp
from tqdm.asyncio import tqdm_asyncio


async def fetch_and_save_release_data(release_url: str, save_path: str) -> dict:
    """异步获取并保存release数据，带进度条"""
    # 确保目录存在
    await asyncio.to_thread(os.makedirs, save_path, exist_ok=True)

    json_path = os.path.join(save_path, "data.json")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Mozilla/5.0"}
    if not os.path.exists(json_path):
        async with aiohttp.ClientSession() as session:
            # 检查文件是否已存在
            if not await asyncio.to_thread(os.path.exists, json_path):
                print("正在获取release数据...")
                async with session.get(release_url, headers=headers) as response:
                    response.raise_for_status()
                    chunks = []
                    async for chunk in response.content.iter_chunked(1024):
                        chunks.append(chunk)

                    # 保存文件
                    async with aiofiles.open(json_path, "wb") as f:
                        await f.write(b"".join(chunks))

    # 读取JSON文件
    async with aiofiles.open(json_path, "r", encoding="utf-8") as f:
        content = await f.read()
        return json.loads(content)


async def download_asset(
    session: aiohttp.ClientSession,
    url: str,
    filepath: str,
    expected_size: int,
    semaphore: asyncio.Semaphore,
    progress: tqdm_asyncio,
) -> bool:
    """下载单个asset文件，带校验和断点续传"""
    async with semaphore:
        filename = os.path.basename(filepath)
        temp_filepath = f"{filepath}.downloading"

        # 检查文件是否已完整下载
        if os.path.exists(filepath):
            actual_size = os.path.getsize(filepath)
            if actual_size == expected_size:
                if progress:
                    progress.update(1)
                return True
            print(
                f"文件不完整，重新下载: {filename} (现有大小: {actual_size}, 预期大小: {expected_size})"
            )
            os.remove(filepath)

        # 创建下载目录
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # 检查是否有部分下载的临时文件
        resume_position = 0
        if os.path.exists(temp_filepath):
            resume_position = os.path.getsize(temp_filepath)
            if resume_position > expected_size:
                os.remove(temp_filepath)
                resume_position = 0

        headers = {}
        if resume_position > 0:
            headers["Range"] = f"bytes={resume_position}-"
            print(f"恢复下载: {filename} (从 {resume_position} 字节开始)")
        else:
            print(f"开始下载: {filename} (大小: {expected_size / 1024 / 1024:.2f} MB)")

        try:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()

                mode = "ab" if resume_position > 0 else "wb"
                async with aiofiles.open(temp_filepath, mode) as f:
                    async for chunk in response.content.iter_chunked(
                        1024 * 1024
                    ):  # 1MB chunks
                        await f.write(chunk)

                # 下载完成后校验大小
                actual_size = os.path.getsize(temp_filepath)
                if actual_size != expected_size:
                    print(
                        f"大小校验失败: {filename} (实际: {actual_size}, 预期: {expected_size})"
                    )
                    os.remove(temp_filepath)
                    return False

                # 重命名临时文件为正式文件
                os.rename(temp_filepath, filepath)
                if progress:
                    progress.update(1)
                return True

        except Exception as e:
            print(f"下载出错 {filename}: {str(e)}")
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            return False


async def main(release_url: str, save_path: str, max_concurrent: int):
    """主函数"""
    try:
        # 获取Release数据
        print("正在获取Release信息...")
        release_data = await fetch_and_save_release_data(release_url, save_path)

        # 准备下载任务
        assets = release_data.get("assets", [])
        if not assets:
            print("该Release没有包含任何assets")
            return

        print(f"找到 {len(assets)} 个assets")

        # 创建进度条
        with tqdm_asyncio(
            total=len(assets), desc="总下载进度", unit="文件"
        ) as progress:
            # 创建信号量控制并发数
            semaphore = asyncio.Semaphore(max_concurrent)

            # 创建session并开始下载
            async with aiohttp.ClientSession() as session:
                tasks = []
                for asset in assets:
                    url = asset["browser_download_url"]
                    filename = asset["name"]
                    size = asset["size"]
                    filepath = os.path.join(save_path, filename)

                    task = asyncio.create_task(
                        download_asset(
                            session, url, filepath, size, semaphore, progress
                        )
                    )
                    tasks.append(task)

                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 统计结果
                success_count = sum(1 for r in results if r is True)
                failed_count = len(assets) - success_count

                print(f"\n下载完成: 成功 {success_count}/{len(assets)}")
                if failed_count > 0:
                    print(f"失败 {failed_count} 个文件，请检查日志")

    except Exception as e:
        print(f"程序出错: {str(e)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GitHub Release Assets下载工具")
    parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="GitHub Release API URL，如: https://api.github.com/repos/msys2/msys2-archive/releases/tags/2022-12-16-mingw64",
    )
    parser.add_argument("--path", type=str, required=True, help="保存路径")
    parser.add_argument(
        "--concurrent", type=int, default=5, help="最大并发下载数 (默认: 5)"
    )

    args = parser.parse_args()

    print("GitHub Release下载器")
    print(f"Release URL: {args.url}")
    print(f"保存路径: {args.path}")
    print(f"最大并发数: {args.concurrent}")
    print("-" * 50)

    asyncio.run(main(args.url, args.path, args.concurrent))
