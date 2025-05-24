import os
import re
import aiohttp
import asyncio
from urllib.parse import urljoin
from tqdm import tqdm

# 全局配置
CONCURRENCY = 50
TIMEOUT = aiohttp.ClientTimeout(total=60 * 5)
RETRIES = 5


async def download_file(session, semaphore, url, save_path, pbar):
    async with semaphore:
        for attempt in range(RETRIES):
            try:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                async with session.get(url, timeout=TIMEOUT) as response:
                    if response.status == 200:
                        with open(save_path, "wb") as f:
                            async for chunk in response.content.iter_chunked(
                                1024 * 1024
                            ):
                                f.write(chunk)
                        pbar.update(1)
                        return True
                    print(
                        f"Attempt {attempt + 1} failed for {url}: HTTP {response.status}"
                    )
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                print(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
            except Exception as e:
                print(f"Unexpected error for {url}: {str(e)}")
                break
        return False


async def download_files(base_url, download_dir, file_paths):
    connector = aiohttp.TCPConnector(
        limit=CONCURRENCY,
        force_close=True,
        enable_cleanup_closed=True,
    )

    async with aiohttp.ClientSession(
        connector=connector, timeout=TIMEOUT, trust_env=True
    ) as session:
        semaphore = asyncio.Semaphore(CONCURRENCY)
        file_paths = [
            file_path for file_path in file_paths if "debuginfo" not in file_path
        ]
        with tqdm(total=len(file_paths), desc="Downloading") as pbar:
            tasks = []
            for file_path in file_paths:
                # save_name = (
                #     file_path.replace(".tar.xz", ".hint")
                #     .replace(".tar.bz2", ".hint")
                #     .replace(".tar.zst", ".hint")
                # )
                # url = urljoin(base_url, save_name)
                url = urljoin(base_url, file_path)
                save_path = os.path.join(download_dir, file_path)
                tasks.append(download_file(session, semaphore, url, save_path, pbar))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            success = sum(1 for r in results if r is True)
            print(
                f"\nDownload complete: {success} succeeded, {len(file_paths) - success} failed"
            )


def extract_file_paths(file_content):
    pattern = r"^(install|source):\s+(\S+)"
    matches = re.finditer(pattern, file_content, re.MULTILINE)
    return [match.group(2).split()[0] for match in matches]


def read_setup_ini(file_path="setup.ini"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: File {file_path} not found in current directory")
        return None
    except Exception as e:
        print(f"Error reading {file_path}: {str(e)}")
        return None


async def main():
    file_content = read_setup_ini()
    if file_content is None:
        return

    base_url = "http://ctm.crouchingtigerhiddenfruitbat.org/pub/cygwin/circa/64bit/2024/01/30/231215/"
    download_dir = os.path.join(os.path.dirname(__file__), "hints")

    file_paths = extract_file_paths(file_content)
    print(f"Found {len(file_paths)} files to download")
    await download_files(base_url, download_dir, file_paths)


if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
