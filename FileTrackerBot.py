import os
import json
import zipfile
import asyncio
import logging
from datetime import datetime
from telethon import TelegramClient, events

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load settings from settings.json
with open("settings.json", "r") as settings_file:
    settings = json.load(settings_file)

api_id = settings["api_id"]
api_hash = settings["api_hash"]
bot_token = settings["bot_token"]
admin_user_id = settings["admin_user_id"]
folder_paths = settings["folder_paths"]
check_interval = 300  # 5 minutes in seconds

# Create an instance of TelegramClient
client = TelegramClient("FileTrackerBot", api_id, api_hash).start(bot_token=bot_token)

# Variables to keep track of the last check time and new files found
last_check_time = datetime.now()
new_files_found = False


async def show_welcome(event):
    """Display a welcome message and instructions."""
    sender_id = event.sender_id
    sender_username = event.sender.username
    if sender_id == admin_user_id:
        welcome_message = (
            "Welcome to the File Tracker Bot!\n\n"
            "Use the following commands:\n\n"
            "/files - Display files in the specified folders\n"
            "/check - Check for new files in the specified folders\n"
            "/download [file_path] - Download a file\n"
            "/delete [file_path] - Delete a file\n"
            "/all - Download all available media files\n"
            "/zip - Create zip files containing files from specified folders\n"
        )
        await client.send_message(sender_id, welcome_message)
    else:
        access_denied_message = (
            "Access Denied!\n\n"
            "You are not authorized to use this bot. This bot is designed to be used only by the authorized user."
        )
        await client.send_message(sender_id, access_denied_message)

        admin_notification = (
            f"🚨 Unauthorized Access Attempt 🚨\n\n"
            f" User {sender_username}, with this ({sender_id}) user id\n"
            "Attempted to access the File Tracker Bot.\n\n"
            "Please take appropriate action if necessary."
        )
        await client.send_message(admin_user_id, admin_notification)


async def list_files(event):
    """List files in the specified folders."""
    if event.sender_id == admin_user_id:
        files_list = "Files in specified folders:\n\n"
        for folder_path in folder_paths:
            files_list += f"{folder_path}:\n"
            try:
                for file_name in os.listdir(folder_path):
                    files_list += f"  {file_name}\n"
            except Exception as e:
                files_list += f"  Error reading folder: {str(e)}\n"
        await event.respond(files_list)
    else:
        await event.respond("Access Denied!")


async def check_new_files(current_files):
    """Check for new files in the specified folders."""
    global new_files_found
    new_files_found = False
    for folder_path in folder_paths:
        new_files = set(os.listdir(folder_path)) - current_files[folder_path]
        if new_files:
            new_files_found = True
            for file_name in new_files:
                file_path = os.path.join(folder_path, file_name)
                try:
                    await client.send_file(
                        admin_user_id,
                        file_path,
                        caption=f"New file created: `{file_path}`",
                        parse_mode="markdown",
                    )
                    logger.info(f"New file sent: {file_path}")
                except Exception as e:
                    await client.send_message(
                        admin_user_id, f"Error sending file: {str(e)}"
                    )
                    logger.error(f"Error sending file: {file_path} - {str(e)}")
            current_files[folder_path] = set(os.listdir(folder_path))
    return new_files_found


async def monitor_folders():
    """Monitor folders for new files."""
    global last_check_time
    current_files = {
        folder_path: set(os.listdir(folder_path)) for folder_path in folder_paths
    }
    while True:
        await check_new_files(current_files)
        last_check_time = datetime.now()
        await asyncio.sleep(check_interval)


@client.on(events.NewMessage(pattern="/start"))
async def handle_start(event):
    await show_welcome(event)


@client.on(events.NewMessage(pattern="/files"))
async def handle_files(event):
    await list_files(event)


@client.on(events.NewMessage(pattern="/check"))
async def handle_check(event):
    """Force a check for new files in the specified folders."""
    if event.sender_id == admin_user_id:
        global last_check_time
        current_files = {
            folder_path: set(os.listdir(folder_path)) for folder_path in folder_paths
        }
        await check_new_files(current_files)
        last_check_time = datetime.now()
        await event.respond("Folders have been checked for new files.")
        logger.info("Folders checked for new files.")
    else:
        await event.respond("Access Denied!")


@client.on(events.NewMessage(pattern=r"/download (.+)"))
async def handle_download(event):
    """Download a specified file."""
    if event.sender_id == admin_user_id:
        file_path = event.pattern_match.group(1)
        if os.path.isfile(file_path):
            try:
                await client.send_file(admin_user_id, file_path)
                await event.respond(f"File sent: {file_path}")
                logger.info(f"File sent: {file_path}")
            except Exception as e:
                await event.respond(f"Error sending file: {str(e)}")
                logger.error(f"Error sending file: {file_path} - {str(e)}")
        else:
            await event.respond("File not found!")
            logger.warning(f"File not found: {file_path}")
    else:
        await event.respond("Access Denied!")


@client.on(events.NewMessage(pattern=r"/delete (.+)"))
async def handle_delete(event):
    """Delete a specified file."""
    if event.sender_id == admin_user_id:
        file_path = event.pattern_match.group(1)
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
                await event.respond(f"File deleted: {file_path}")
                logger.info(f"File deleted: {file_path}")
            except Exception as e:
                await event.respond(f"Error deleting file: {str(e)}")
                logger.error(f"Error deleting file: {file_path} - {str(e)}")
        else:
            await event.respond("File not found!")
            logger.warning(f"File not found: {file_path}")
    else:
        await event.respond("Access Denied!")


@client.on(events.NewMessage(pattern="/all"))
async def handle_all(event):
    """Download all available media files as a zip."""
    if event.sender_id == admin_user_id:
        zip_file_path = "all_media_files.zip"
        with zipfile.ZipFile(zip_file_path, "w") as zip_file:
            for folder_path in folder_paths:
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if file_path.lower().endswith((".mp4", ".avi", ".mkv")):
                            zip_file.write(
                                file_path, os.path.relpath(file_path, folder_path)
                            )
        try:
            await client.send_file(
                admin_user_id, zip_file_path, caption="All media files"
            )
            os.remove(zip_file_path)
            logger.info("All media files sent as zip.")
        except Exception as e:
            await event.respond(f"Error sending zip file: {str(e)}")
            logger.error(f"Error sending zip file: {str(e)}")
    else:
        await event.respond("Access Denied!")


@client.on(events.NewMessage(pattern="/zip"))
async def handle_zip(event):
    """Create a zip file containing files from specified folders."""
    if event.sender_id == admin_user_id:
        zip_file_path = "specified_folders.zip"
        with zipfile.ZipFile(zip_file_path, "w") as zip_file:
            for folder_path in folder_paths:
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        zip_file.write(
                            file_path, os.path.relpath(file_path, folder_path)
                        )
        try:
            await client.send_file(
                admin_user_id, zip_file_path, caption="Specified folders zipped"
            )
            os.remove(zip_file_path)
            logger.info("Specified folders zipped and sent.")
        except Exception as e:
            await event.respond(f"Error sending zip file: {str(e)}")
            logger.error(f"Error sending zip file: {str(e)}")
    else:
        await event.respond("Access Denied!")


# Start the bot and the folder monitoring task
client.loop.create_task(monitor_folders())
print("Bot is ready to receive commands.")
client.run_until_disconnected()
