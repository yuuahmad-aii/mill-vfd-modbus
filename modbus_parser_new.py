'''
This script parses Modbus data from a CSV file where each row represents a byte.
It groups bytes into messages based on timestamps and interprets the messages.
'''

import csv

def parse_modbus_messages(hex_string):
    """Parses a Modbus message and returns its interpretation."""
    if hex_string.startswith("010600020001"):
        return "Perintah berputar ke kanan"
    elif hex_string.startswith("010600020002"):
        return "Perintah berputar ke kiri"
    elif hex_string.startswith("010600020004"):
        return "Perintah berhenti"
    elif hex_string.startswith("01060004"):
        speed_hex = hex_string[8:12]
        speed_int = int(speed_hex, 16)
        return f"Memutar spindle dengan kecepatan {speed_int}"
    elif hex_string.startswith("010301080001"):
        return "Request kecepatan spindle"
    else:
        return "Perintah tidak dikenal"

def group_and_parse_from_file(filename):
    """Reads a CSV file, groups bytes into messages, and parses them."""
    with open(filename, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)  # Skip header

        messages = []
        current_message_bytes = []
        last_time = None

        for row in reader:
            try:
                time_str, value_str = row[0], row[1]
                current_time = float(time_str)
                byte_val = value_str.strip().replace("0x", "")

                if last_time is not None and current_time - last_time > 0.1:  # Threshold to detect new message
                    if current_message_bytes:
                        messages.append("".join(current_message_bytes))
                    current_message_bytes = []

                current_message_bytes.append(byte_val)
                last_time = current_time
            except (ValueError, IndexError):
                # Skip rows with formatting issues
                continue

        if current_message_bytes:
            messages.append("".join(current_message_bytes))

        for msg in messages:
            print(f"Data: {msg}, Terjemahan: {parse_modbus_messages(msg)}")

if __name__ == "__main__":
    # The new data file is 'data.txt', which is also in CSV format.
    group_and_parse_from_file("data.txt")
