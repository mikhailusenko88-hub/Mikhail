"""Выкладка ролика в сообщество VK.

Сначала пробуем загрузить как клип (shortVideo.*). Эти методы VK официально почти
не документирует, поэтому если что-то не так — автоматически загружаем как обычное
вертикальное видео в сообщество (video.save) с дублем на стену.
"""
import os
import time

import requests

API = "https://api.vk.ru/method/"
V = "5.199"


class VKError(Exception):
    pass


def call(method, **params):
    params.update(access_token=os.environ["VK_TOKEN"], v=V)
    r = requests.post(API + method, data=params, timeout=60).json()
    if "error" in r:
        e = r["error"]
        raise VKError(f"{method}: {e.get('error_code')} {e.get('error_msg')}")
    return r["response"]


def _upload(url, field, path):
    with open(path, "rb") as f:
        r = requests.post(url, files={field: (os.path.basename(path), f, "video/mp4")}, timeout=600)
    r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        return {}


def as_clip(path, group_id, description, wallpost=True, log=print):
    size = os.path.getsize(path)
    resp = call("shortVideo.create", group_id=group_id, file_size=size,
                description=description, wallpost=int(wallpost))
    try:
        up = _upload(resp["upload_url"], "file", path)
    except Exception as e:
        raise VKError(f"загрузка файла клипа: {e}")
    # дальше файл уже у VK: ошибки ниже не приводят к повторной загрузке (без дублей)
    owner_id = resp.get("owner_id", -group_id)
    video_id = resp.get("video_id") or up.get("video_id")
    # ждём обработку и публикуем
    for _ in range(40):
        try:
            prog = call("shortVideo.encodeProgress", owner_id=owner_id, video_id=video_id)
            if prog.get("is_ready") or prog.get("percents", 0) >= 100:
                break
        except VKError:
            break
        time.sleep(6)
    try:
        call("shortVideo.publish", owner_id=owner_id, video_id=video_id,
             license_agree=1, wallpost=int(wallpost))
    except VKError as e:
        log(f"shortVideo.publish: {e} (возможно, клип опубликован сразу)")
    return f"https://vk.ru/clip{owner_id}_{video_id}"


def as_video(path, group_id, title, description, wallpost=True):
    resp = call("video.save", group_id=group_id, name=title[:128], description=description,
                wallpost=int(wallpost), repeat=0)
    up = _upload(resp["upload_url"], "video_file", path)
    owner_id = resp.get("owner_id", -group_id)
    video_id = resp.get("video_id") or up.get("video_id")
    return f"https://vk.ru/video{owner_id}_{video_id}"


def upload(path, title, description, cfg, log=print):
    group_id = int(cfg.get("vk_group_id") or os.environ.get("VK_GROUP_ID", 0))
    if not group_id:
        raise RuntimeError("Не указан vk_group_id (номер сообщества) в config.json")
    wallpost = cfg.get("vk_wallpost", True)
    mode = cfg.get("vk_mode", "clip")
    if mode == "clip":
        try:
            return as_clip(path, group_id, description, wallpost, log), "клип"
        except VKError as e:
            # сюда попадаем, только если файл ещё не ушёл в VK
            log(f"Как клип не вышло ({e}), загружаю как видео")
    return as_video(path, group_id, title, description, wallpost), "видео"
