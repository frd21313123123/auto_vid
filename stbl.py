import os
import time
import json
import requests
from moviepy.editor import VideoFileClip, AudioFileClip
import google.generativeai as genai

def load_api_keys(file_path):
    """Читает API-ключи из файла и возвращает их в виде словаря."""
    api_keys = {}
    with open(file_path, 'r') as file:
        for line in file:
            key, value = line.strip().split('=', 1)
            api_keys[key.strip()] = value.strip().strip('"')
    return api_keys

# Загрузка API-ключей из файла
api_keys = load_api_keys('api.txt')

# Ваш API-ключи Google Gemini и EdenAI
google_api_key = api_keys['google']
ed_api_key = api_keys['ed']

# Конфигурация Google Gemini
genai.configure(api_key=google_api_key)

def upload_to_gemini(path, mime_type=None):
    """Загружает указанный файл в Gemini."""
    file = genai.upload_file(path, mime_type=mime_type)
    print(f"Файл '{file.display_name}' загружен как: {file.uri}")
    return file

def wait_for_files_active(files):
    """Ожидает, пока указанные файлы будут активны."""
    print("Ожидание обработки файлов...")
    for name in (file.name for file in files):
        file = genai.get_file(name)
        while file.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(10)
            file = genai.get_file(name)
        if file.state.name != "ACTIVE":
            raise Exception(f"Файл {file.name} не удалось обработать")
    print("...все файлы готовы")
    print()

# Настройки модели
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,

)

def get_video_summary(video_path):
    # Загрузка видео файла
    file = upload_to_gemini(video_path, mime_type="video/mp4")

    # Ожидание, пока файл будет готов к использованию
    wait_for_files_active([file])

    # Начало сессии чата и отправка видео для анализа
    chat_session = model.start_chat(
        history=[
            {
                "role": "user",
                "parts": [
                    file,
                ],
            },
            {
                "role": "user",
                "parts": [
                    "Сделайте объемную сводку этого видео.\n",
                ],
            },
        ]
    )

    # Получение ответа
    response = chat_session.send_message("Сделайте объемную сводку этого видео. Объясните все в деталях.")
    return response.text

def text_to_speech(text='В этом видео'):
    headers = {
        "Authorization": f"Bearer {ed_api_key}"
    }

    url = 'https://api.edenai.run/v2/audio/text_to_speech'

    payload = {
        "providers": "openai/ru_alloy",
        "language": "ru-RU",
        "option": "MALE",
        "text": f"{text}",
    }

    response = requests.post(url, json=payload, headers=headers)
    result = json.loads(response.text)
    unx_time = int(time.time())

    json_file_path = f'{unx_time}.json'
    with open(json_file_path, 'w') as file:
        json.dump(result, file, indent=4, ensure_ascii=False)

    audio_url = result.get('openai/ru_alloy').get('audio_resource_url')
    r = requests.get(audio_url)

    audio_file_path = f'{unx_time}.wav'
    with open(audio_file_path, 'wb') as file:
        file.write(r.content)

    return json_file_path, audio_file_path

def replace_audio_in_video(video_path, audio_path, output_path):
    """Заменяет аудиодорожку в видеофайле на новую аудиофайл и обрезает видео до конца аудио."""
    video_clip = VideoFileClip(video_path)
    audio_clip = AudioFileClip(audio_path)

    # Длительность аудио
    audio_duration = audio_clip.duration

    # Обрезаем видео до длительности аудио
    video_clip = video_clip.subclip(0, audio_duration)

    # Заменяем аудио дорожку
    video_with_new_audio = video_clip.set_audio(audio_clip)
    video_with_new_audio.write_videofile(output_path, codec='libx264', audio_codec='aac')
    video_clip.close()
    audio_clip.close()
    video_with_new_audio.close()

def delete_files(*file_paths):
    """Удаляет указанные файлы."""
    for file_path in file_paths:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Файл {file_path} удалён.")
        else:
            print(f"Файл {file_path} не найден.")

def main():
    video_path = input("Введите путь к видео файлу: ")
    if os.path.exists(video_path):
        print("Загрузка видео и получение сводки...")
        summary = get_video_summary(video_path)
        print("Сводка видео:")
        print(summary)
        print("Генерация речи из текста...")
        json_path, audio_path = text_to_speech(text=summary)
        output_video_path = f"modified_{os.path.basename(video_path)}"
        print(f"Заменяем аудио в видео и сохраняем как {output_video_path}...")
        replace_audio_in_video(video_path, audio_path, output_video_path)
        print(f"Готово! Видео сохранено как {output_video_path}")

        # Удаление временных файлов
        delete_files(json_path, audio_path)
    else:
        print("Видео файл не найден. Пожалуйста, проверьте путь к файлу.")

if __name__ == '__main__':
    main()
