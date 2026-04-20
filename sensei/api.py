import requests
from tqdm import tqdm
import os
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event, Lock

class Api:
    def __init__(self, api_key, destination=None):
        self.api_key = api_key
        if os.getenv('SENSEI_ENV') == 'local':
            print("Using local API endpoint")
            self.api_root = "http://127.0.0.1:8000/datasets/"
        else:
            self.api_root = "https://api.senseirobotics.com/datasets/"
        self.destination = destination
        self._cancel_event = Event()

    def make_request(self, url, include_root=True):
        response = requests.get(f"{self.api_root if include_root else ''}{url}", headers={"Authorization": f"ApiKey {self.api_key}"})
        if response.status_code == 403:
            raise RuntimeError("Authentication failed. Check your API key.")
        return response.json()

    def _iter_results(self, url, include_root=True):
        """
        Iterates over a paginated API response
        """
        response = self.make_request(url, include_root=include_root)
        yield from response["results"]
        if response["next"]:
            yield from self._iter_results(response["next"], include_root=False)

    def iter_files(self, path="/"):
        """
        Iterates over files in given directory (defaults to root directory)
        """
        return self._iter_results(f"files/?parent={path}")

    def iter_dirs(self, path="/"):
        """
        Iterates over directories in given directory (defaults to root directory)
        """
        return self._iter_results(f"paths/?parent={path}")
    
    def get_file(self, path):
        """
        Gets API info of file at given path
        """
        path_parts = path.split("/")
        filename = path_parts[-1]
        filepath = "/".join(path_parts[:-1])
        response = self.make_request(f"files/?parent={filepath}&filename={filename}")
        if response["count"] == 0:
            raise FileNotFoundError()
        assert response["count"] == 1
        return response["results"][0]
    
    def get_file_details(self, file_id):
        """
        Gets API info of file with given ID
        """
        return self.make_request(f"files/{file_id}/")
    
    def _download_file(self, filepath, file, overwrite=False, progress=None, progress_lock=None):
        """
        Downloads the file
        """
        if not self.destination:
            raise RuntimeError("To download files, pass in a destination to the Api class constructor")

        dest_filepath = os.path.join(self.destination, filepath)

        file_details = self.get_file_details(file["id"])

        aggregated = progress is not None
        notify = tqdm.write if aggregated else print

        if not aggregated:
            print("Downloading to", dest_filepath)
        os.makedirs(os.path.dirname(dest_filepath), exist_ok=True)
        if os.path.isfile(dest_filepath):
            if overwrite:
                if not aggregated:
                    print("Overwriting")
            else:
                notify(f"WARNING: File already exists, skipping: {dest_filepath}. Set overwrite=True to overwrite")
                return

        if not file_details.get("download_link"):
            notify(f"File not available to download, skipping: {dest_filepath}")
            return

        if self._cancel_event.is_set():
            return

        response = requests.get(file_details["download_link"], stream=True)
        CHUNK_SIZE = 1024 * 1024  # 1MB
        partial_path = dest_filepath + ".part"

        try:
            if aggregated:
                content_length = int(response.headers['Content-Length'])
                with progress_lock:
                    progress.total += content_length
                    progress.refresh()
                with open(partial_path, "wb") as handle:
                    for data in response.iter_content(chunk_size=CHUNK_SIZE):
                        if self._cancel_event.is_set():
                            raise KeyboardInterrupt()
                        handle.write(data)
                        progress.update(len(data))
            else:
                num_chunks = math.ceil(int(response.headers['Content-Length'])/CHUNK_SIZE)
                with open(partial_path, "wb") as handle:
                    for data in tqdm(response.iter_content(chunk_size=CHUNK_SIZE), unit='MB', total=num_chunks):
                        handle.write(data)
            os.replace(partial_path, dest_filepath)
        except BaseException:
            try:
                os.remove(partial_path)
            except OSError:
                pass
            raise

    def download_file_from_path(self, path, overwrite=False):
        file = self.get_file(path)
        return self._download_file(path, file, overwrite=overwrite)

    def recursive_download(self, path="/", overwrite=False, max_workers=8):
        """
        Recursively download all files in given folder
        """
        self._cancel_event.clear()
        progress_lock = Lock()
        with ThreadPoolExecutor(max_workers=max_workers) as executor, \
             tqdm(total=0, unit='B', unit_scale=True, desc="Downloading") as progress:
            futures = []
            file_found = self._schedule_recursive_download(
                executor, futures, path, overwrite, progress, progress_lock,
            )
            try:
                for future in as_completed(futures):
                    future.result()
            except KeyboardInterrupt:
                self._cancel_event.set()
                for f in futures:
                    f.cancel()
                raise
        return file_found

    def _schedule_recursive_download(self, executor, futures, path, overwrite, progress, progress_lock):
        tqdm.write(f"Downloading from {path}...")
        file_found = False
        for file in self.iter_files(path):
            futures.append(executor.submit(
                self._download_file,
                os.path.join(path, file["filename"]),
                file,
                overwrite=overwrite,
                progress=progress,
                progress_lock=progress_lock,
            ))
            file_found = True

        for folder in self.iter_dirs(path):
            self._schedule_recursive_download(
                executor, futures, folder["path"], overwrite, progress, progress_lock,
            )
            file_found = True

        return file_found


