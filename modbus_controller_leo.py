
import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports

def crc16(data: bytes) -> int:
    """
    Menghitung CRC16 untuk data Modbus.
    """
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if (crc & 1) != 0:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc

class ModbusControllerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Modbus Spindle Controller")
        self.root.geometry("450x450")
        self.serial_port = None
        self.rpm_value = 0

        # Style
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Connection Settings ---
        settings_frame = ttk.LabelFrame(main_frame, text="Connection Settings", padding="10")
        settings_frame.pack(fill=tk.X, pady=5)
        settings_frame.grid_columnconfigure(1, weight=1)

        # COM Port
        ttk.Label(settings_frame, text="COM Port:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.com_port_var = tk.StringVar()
        self.com_port_combo = ttk.Combobox(settings_frame, textvariable=self.com_port_var, state='readonly')
        self.com_port_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        self.refresh_ports()
        
        refresh_button = ttk.Button(settings_frame, text="Refresh", command=self.refresh_ports)
        refresh_button.grid(row=0, column=2, padx=5, pady=5)

        # Baudrate
        ttk.Label(settings_frame, text="Baudrate:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.baudrate_var = tk.StringVar(value='9600')
        baudrate_combo = ttk.Combobox(settings_frame, textvariable=self.baudrate_var, state='readonly',
                                      values=['9600', '19200', '38400', '57600', '115200'])
        baudrate_combo.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky=tk.EW)

        # Parity
        ttk.Label(settings_frame, text="Parity:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.parity_var = tk.StringVar(value='None')
        parity_combo = ttk.Combobox(settings_frame, textvariable=self.parity_var, state='readonly',
                                    values=['None', 'Even', 'Odd'])
        parity_combo.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky=tk.EW)

        # Stop Bits
        ttk.Label(settings_frame, text="Stop Bits:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        self.stopbits_var = tk.StringVar(value='1')
        stopbits_combo = ttk.Combobox(settings_frame, textvariable=self.stopbits_var, state='readonly',
                                      values=['1', '1.5', '2'])
        stopbits_combo.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky=tk.EW)

        # Connect/Disconnect Buttons
        connect_frame = ttk.Frame(main_frame)
        connect_frame.pack(fill=tk.X, pady=5)
        connect_frame.grid_columnconfigure((0, 1), weight=1)

        self.connect_button = ttk.Button(connect_frame, text="Connect", command=self.connect)
        self.connect_button.grid(row=0, column=0, padx=5, sticky=tk.EW)
        self.disconnect_button = ttk.Button(connect_frame, text="Disconnect", command=self.disconnect, state=tk.DISABLED)
        self.disconnect_button.grid(row=0, column=1, padx=5, sticky=tk.EW)

        # --- Spindle Control Buttons ---
        control_frame = ttk.LabelFrame(main_frame, text="Spindle Control", padding="10")
        control_frame.pack(fill=tk.X, pady=5)
        control_frame.grid_columnconfigure((0, 1, 2), weight=1)

        cw_button = ttk.Button(control_frame, text="Putar CW", command=lambda: self.send_modbus_command("010660000001"))
        cw_button.grid(row=0, column=0, padx=5, pady=5, sticky=tk.EW)

        ccw_button = ttk.Button(control_frame, text="Putar CCW", command=lambda: self.send_modbus_command("010660000002"))
        ccw_button.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)

        stop_button = ttk.Button(control_frame, text="Hentikan", command=lambda: self.send_modbus_command("010660000005"))
        stop_button.grid(row=0, column=2, padx=5, pady=5, sticky=tk.EW)

        # --- RPM Control ---
        rpm_frame = ttk.LabelFrame(main_frame, text="RPM Control", padding="10")
        rpm_frame.pack(fill=tk.X, pady=5)
        rpm_frame.grid_columnconfigure(1, weight=1)

        self.rpm_var = tk.StringVar(value=str(self.rpm_value))
        
        rpm_minus_button = ttk.Button(rpm_frame, text="-", command=self.decrease_rpm, width=5)
        rpm_minus_button.grid(row=0, column=0, padx=5, pady=5)

        rpm_label = ttk.Label(rpm_frame, textvariable=self.rpm_var, font=("Helvetica", 12, "bold"))
        rpm_label.grid(row=0, column=1, padx=5, pady=5)

        rpm_plus_button = ttk.Button(rpm_frame, text="+", command=self.increase_rpm, width=5)
        rpm_plus_button.grid(row=0, column=2, padx=5, pady=5)
        
        send_rpm_button = ttk.Button(rpm_frame, text="Kirim RPM", command=self.send_rpm_command)
        send_rpm_button.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky=tk.EW)


        # --- Status Bar ---
        self.status_var = tk.StringVar(value="Status: Disconnected")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=5)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def increase_rpm(self):
        self.rpm_value = min(100, self.rpm_value + 10)
        self.rpm_var.set(str(self.rpm_value))

    def decrease_rpm(self):
        self.rpm_value = max(0, self.rpm_value - 10)
        self.rpm_var.set(str(self.rpm_value))

    def send_rpm_command(self):
        # Multiply RPM value by 100 for 2-decimal precision (e.g., GUI value 100 -> 10000)
        value_to_send = self.rpm_value * 100
        # Format the new value as a 4-digit hex string (e.g., 10000 -> 2710)
        rpm_hex = f"{value_to_send:04x}"
        command = f"01065000{rpm_hex}"
        self.send_modbus_command(command)

    def refresh_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.com_port_combo['values'] = ports
        if ports:
            self.com_port_var.set(ports[0])

    def connect(self):
        if self.serial_port and self.serial_port.is_open:
            messagebox.showwarning("Warning", "Already connected.")
            return

        port = self.com_port_var.get()
        if not port:
            messagebox.showerror("Error", "No COM port selected.")
            return

        baud = int(self.baudrate_var.get())
        parity_map = {'None': serial.PARITY_NONE, 'Even': serial.PARITY_EVEN, 'Odd': serial.PARITY_ODD}
        parity = parity_map[self.parity_var.get()]
        stopbits_map = {'1': serial.STOPBITS_ONE, '1.5': serial.STOPBITS_ONE_POINT_FIVE, '2': serial.STOPBITS_TWO}
        stopbits = stopbits_map[self.stopbits_var.get()]

        try:
            self.serial_port = serial.Serial(port, baud, parity=parity, stopbits=stopbits, timeout=1)
            self.status_var.set(f"Status: Connected to {port} at {baud} bps")
            self.connect_button.config(state=tk.DISABLED)
            self.disconnect_button.config(state=tk.NORMAL)
            messagebox.showinfo("Success", f"Successfully connected to {port}.")
        except serial.SerialException as e:
            messagebox.showerror("Connection Error", f"Failed to connect to {port}:\n{e}")
            self.serial_port = None

    def disconnect(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.status_var.set("Status: Disconnected")
            self.connect_button.config(state=tk.NORMAL)
            self.disconnect_button.config(state=tk.DISABLED)
        
    def send_modbus_command(self, command_hex: str):
        if not self.serial_port or not self.serial_port.is_open:
            messagebox.showerror("Error", "Not connected to any device.")
            return

        try:
            # Convert hex string to bytes
            data = bytes.fromhex(command_hex)
            
            # Calculate CRC and append it (little-endian)
            crc = crc16(data)
            crc_bytes = crc.to_bytes(2, byteorder='little')
            
            # Final command
            full_command = data + crc_bytes
            
            # Send the command
            self.serial_port.write(full_command)
            
            sent_command_hex = full_command.hex().upper()
            self.status_var.set(f"Sent: {sent_command_hex}")
            print(f"Sent: {sent_command_hex}")

        except Exception as e:
            messagebox.showerror("Send Error", f"Failed to send command:\n{e}")
            self.disconnect()

    def on_closing(self):
        self.disconnect()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ModbusControllerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
