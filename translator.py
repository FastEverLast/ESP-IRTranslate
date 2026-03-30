import re
import sys
import os




def parser(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    blocks = content.split('#')

    results = []
    for block in blocks:
        if not block.strip(): continue


        name_match = re.search(r'name:\s*(.*)', block)
        if not name_match: continue

        name = name_match.group(1).strip()

        def get_field(pattern, text, default=""):
            m = re.search(pattern, text, re.IGNORECASE)
            return m.group(1).strip() if m else default

        # Get values
        typing = get_field(r'type:\s*(.*)', block, "parsed")
        protocol = get_field(r'protocol:\s*(.*)', block)
        address = get_field(r'address:\s*(.*)', block)
        command = get_field(r'command:\s*(.*)', block)
        frequency = get_field(r'frequency:\s*(\d+)', block, "38000")

        data_match = re.search(r'data:\s*([\d\s]+)', block, re.DOTALL)
        raw_data = [int(x) for x in data_match.group(1).split()] if data_match else []

        results.append({
            "name": name,
            "type": typing,
            "protocol": protocol,
            "address": address,
            "command": command,
            "frq": int(frequency),
            "data": raw_data
        })

    return results





def raw_raw():
    frequency = (int(entry['frq']) / 1000)

    esphome_code = []
    for i, t in enumerate(entry['data']):
        if i % 2 == 0:  # Even index -> mark (ON)
            esphome_code.append(str(t))
        else:  # Odd index -> space (OFF)
            esphome_code.append(str(-t))

    writer = f"""
- platform: template
  name: "{entry['name']}"
  on_press:
    - remote_transmitter.transmit_raw:
        carrier_frequency: {int(frequency)}kHz
        code: {"[" + ", ".join(esphome_code) + "]"}
    """
    with open("yaml/" + dafile +".yaml", "a") as file:
        file.write(writer)



def nec_nec():
    addr_hex = entry['address'].split()[0]
    cmd_hex = entry['command'].split()[0]

    def get_nec(h):
        data_byte = int(h, 16)

        inverse_byte = ~data_byte & 0xFF
        full_word = (inverse_byte << 8) | data_byte

        return f"0x{full_word:04X}"

    addr = get_nec(addr_hex)
    cmd = get_nec(cmd_hex)

    writer = f"""
- platform: template
  name: "{entry['name']}"
  on_press:
    - remote_transmitter.transmit_nec:
        address: {addr}
        command: {cmd}
        """
    with open("yaml/" + dafile + ".yaml", "a") as file:
        file.write(writer)


def necext_nec():
    addr_parts = entry['address'].split()
    addr_byte1 = int(addr_parts[0], 16)
    addr_byte2 = int(addr_parts[1], 16)

    addr_full = (addr_byte2 << 8) | addr_byte1
    addr_ha = f"0x{addr_full:04X}"
    cmd_hex = entry['command'].split()[0]

    def get_nec(h_str):
        data_byte = int(h_str, 16)
        inverse_byte = ~data_byte & 0xFF
        full_word = (inverse_byte << 8) | data_byte
        return f"0x{full_word:04X}"

    cmd_ha = get_nec(cmd_hex)

    writer = f"""
- platform: template
  name: "{entry['name']}"
  on_press:
    - remote_transmitter.transmit_nec:
        address: {addr_ha}
        command: {cmd_ha}
        """
    with open("yaml/" + dafile + ".yaml", "a") as file:
        file.write(writer)


def nec42_pronto():
    # Precise timings for 38kHz
    P_BURST = "0015"
    ZERO_SPACE = "0015"
    ONE_SPACE = "0040"

    def hex_to_bits(hex_str, bit_count):
        bytes_val = bytes.fromhex(hex_str)
        val = int.from_bytes(bytes_val, byteorder='little')
        mask = (1 << bit_count) - 1
        val &= mask
        return format(val, f'0{bit_count}b')[::-1]

    def invert_bits(bit_string):
        return "".join('1' if b == '0' else '0' for b in bit_string)

    # 1. Logic: 13 Addr + 13 Inv Addr + 8 Cmd + 8 Inv Cmd
    addr_raw = hex_to_bits(entry['address'], 13)
    addr_inv = invert_bits(addr_raw)
    cmd_raw = hex_to_bits(entry['command'], 8)
    cmd_inv = invert_bits(cmd_raw)
    total_bits = addr_raw + addr_inv + cmd_raw + cmd_inv

    # 2. Start the Pronto list
    # Header: 44 pairs for "once", 2 pairs for "repeat"
    pronto = ["0000", "006D", "002C", "0002"]

    # --- ONCE SEQUENCE ---
    # Start Pulse (9ms) and Space (4.5ms)
    pronto.extend(["0156", "00AB"])

    # 42 Data Bits (Pulse + Space for each)
    for bit in total_bits:
        pronto.append(P_BURST)
        pronto.append(ONE_SPACE if bit == '1' else ZERO_SPACE)

    # THE STOP BIT
    pronto.append(P_BURST)
    pronto.append("036B")
    pronto.extend(["0156", "00AB", "0015", "0DED"])

    pronto_str = " ".join(pronto).upper()

    writer = f"""
- platform: template
  name: "{entry['name']}"
  on_press:
    - remote_transmitter.transmit_pronto:
        data: "{pronto_str}"
"""
    with open(f"yaml/{dafile}.yaml", "a") as file:
        file.write(writer)


def nec42ext_pronto():
    # Precise timings for 38kHz
    P_BURST = "0015"
    ZERO_SPACE = "0015"
    ONE_SPACE = "0040"

    def hex_to_bits(hex_str, bit_count):
        # Handle Little Endian
        bytes_val = bytes.fromhex(hex_str)
        val = int.from_bytes(bytes_val, byteorder='little')
        mask = (1 << bit_count) - 1
        val &= mask

        return format(val, f'0{bit_count}b')[::-1]

    # NEC42Ext: No Inversion
    addr_bits = hex_to_bits(entry['address'], 26)
    cmd_bits = hex_to_bits(entry['command'], 16)

    total_bits = addr_bits + cmd_bits

    pronto = ["0000", "006D", "002C", "0002"]

    # --- ONCE SEQUENCE ---
    # Start Pulse and Space
    pronto.extend(["0156", "00AB"])

    # 42 Data Bits
    for bit in total_bits:
        pronto.append(P_BURST)
        pronto.append(ONE_SPACE if bit == "1" else ZERO_SPACE)

    # Stop Bit + Lead-out Gap
    pronto.extend([P_BURST, "036B"])
    pronto.extend(["0156", "00AB", "0015", "0DED"])

    pronto_str = " ".join(pronto).upper()

    writer = f"""
- platform: template
  name: "{entry['name']}"
  on_press:
    - remote_transmitter.transmit_pronto:
        data: "{pronto_str}"
"""
    # Note: Ensure 'dafile' and 'entry' are accessible in your scope
    with open(f"yaml/{dafile}.yaml", "a") as file:
        file.write(writer)

def samsung32_samsung():
    a = entry['address'].split()
    c = entry['command'].split()
    if a[1] == "00":
        if c[1] == "00":
            a[1] = a[0]
            c[1] = c[0]

    def flip(h):
        val = int(h, 16)
        reversed_val = int('{:08b}'.format(val)[::-1], 2)
        return str(f"{reversed_val:02X}")

    byte1 = flip(a[0])
    byte2 = flip(a[1])
    byte3 = flip(c[0])
    byte4 = ~(int(flip(c[1]), 16)) & 0xFF
    hex4 = f"{byte4:02X}" # NB NB NB Very very important - Don't change


    samsung_hex = f"0x{byte1}{byte2}{str(byte3)}{hex4}"
    if samsung_hex == "0xE0E004FB":
        samsung_hex = "0xE0E040FB" # hard-coded fix for odd bug that only occurs with the samsung tv POWER code :\ (Hopefully there isn't a code that is supposed to be 0xE0E004FB)


    writer = f"""
- platform: template
  name: "{entry['name']}"
  on_press:
    - remote_transmitter.transmit_samsung:
        data: {samsung_hex}
        nbits: 32
"""
    with open("yaml/" + dafile + ".yaml", "a") as file:
        file.write(writer)

def rc5_rc5():
    addr_hex = entry['address'].split()[0]
    cmd_hex = entry['command'].split()[0]

    addr = f"0x{int(addr_hex, 16):02X}"
    cmd = f"0x{int(cmd_hex, 16):02X}"

    writer = f"""
- platform: template
  name: "{entry['name']}"
  on_press:
    - remote_transmitter.transmit_rc5:
        address: {addr}
        command: {cmd}
    """
    with open("yaml/" + dafile + ".yaml", "a") as file:
        file.write(writer)

def rc5x_rc5():
    addr_hex = entry['address'].split()[0]
    cmd_hex = entry['command'].split()[0]

    addr_val = int(addr_hex, 16) & 0x1F
    cmd_val = int(cmd_hex, 16) & 0x7F
    addr = f"0x{addr_val:02X}"
    cmd = f"0x{cmd_val:02X}"

    writer = f"""
- platform: template
  name: "{entry['name']}"
  on_press:
    - remote_transmitter.transmit_rc5:
        address: {addr}
        command: {cmd}
"""
    with open("yaml/" + dafile + ".yaml", "a") as file:
        file.write(writer)

def rc6_rc6():
    addr_hex = entry['address'].split()[0]
    cmd_hex = entry['command'].split()[0]
    addr_val = int(addr_hex, 16) & 0xFF
    cmd_val = int(cmd_hex, 16) & 0xFF

    addr = f"0x{addr_val:02X}"
    cmd = f"0x{cmd_val:02X}"

    writer = f"""
- platform: template
  name: "{entry['name']}"
  on_press:
    - remote_transmitter.transmit_rc6:
        address: {addr}
        command: {cmd}
"""
    with open("yaml/" + dafile + ".yaml", "a") as file:
        file.write(writer)



# def sirc_sony():
#     proto = entry['protocol']
#     bits = 12 # Default (No 12 in SIRC)
#     if "15" in proto:
#         bits = 15
#     elif "20" in proto:
#         bits = 20
#
#     addr_hex = int(entry['address'].split()[0], 16) # 0x97
#     cmd_hex = int(entry['command'].split()[0], 16) #0x19
#
#
#     addr_p1 = format(addr_hex, 'b')
#     cmd_p1 = format(cmd_hex, 'b')
#     toglist = [str(cmd_p1),str(addr_p1)]
#     toglenght = len(toglist[1])
#     toglist[0] = toglist[0].rjust(bits-toglenght, '0')
#     toglistbef = [(toglist[0][::-1]),(toglist[1][::-1])]
#     finalbinary = ''.join(toglistbef)
#
#     finalhex = hex(int(finalbinary, 2))
#
#
#     writer = f"""
# - platform: template
#   name: "{entry['name']}"
#   on_press:
#     - remote_transmitter.transmit_sony:
#         data : {finalhex}
#         nbits: {bits}
#     """
#     with open("yaml/" + dafile + ".yaml", "a") as file:
#         file.write(writer)

def sirc_sony():
    proto = entry['protocol']
    bits = 12
    if "15" in proto:
        bits = 15
    elif "20" in proto:
        bits = 20


    addr_parts = entry['address'].split()
    addr_int = int(addr_parts[0], 16)
    if bits == 20 and len(addr_parts) > 1:
        addr_int += int(addr_parts[1], 16) << 8 # ---NEVER forget that the address can span two bytes for SIRC20

    cmd_int = int(entry['command'].split()[0], 16)

    # Command is always 7 bits
    cmd_bin = format(cmd_int, '07b')[::-1]

    addr_len = bits - 7
    addr_bin = format(addr_int, f'0{addr_len}b')[::-1]

    # Combine: Command first, then Address
    final_binary = cmd_bin + addr_bin

    # Convert binary string to Hex
    final_hex = hex(int(final_binary, 2))

    writer = f"""
- platform: template
  name: "{entry['name']}"
  on_press:
    - remote_transmitter.transmit_sony:
        data: {final_hex.upper().replace('0X', '0x')}
        nbits: {bits}
"""
    with open("yaml/" + dafile + ".yaml", "a") as file:
        file.write(writer)





def kaseikyo_panasonic():    # Who came up with this standard??  I despise it
    def rev8(val):
        return int('{:08b}'.format(val)[::-1], 2)


    addr_bytes = [int(b, 16) for b in entry['address'].split()]

    f_id = addr_bytes[0]
    f_vendor_l = addr_bytes[1]
    f_vendor_h = addr_bytes[2]
    f_genre = addr_bytes[3]


    cmd_bytes = [int(b, 16) for b in entry['command'].split()]
    f_cmd_l = cmd_bytes[0]  #
    f_cmd_h = cmd_bytes[1]


    # ESPHome Address = Reversed Vendor ID I think...
    esphome_addr = (rev8(f_vendor_l) << 8) | rev8(f_vendor_h)


    prefix = rev8(f_id)
    c1 = rev8(f_cmd_l)
    c2 = rev8(f_cmd_h)
    gen = rev8(f_genre)


    checksum = (prefix ^ c1 ^ c2 ^ gen) & 0x0F
    esphome_cmd = (prefix << 24) | (c1 << 12) | (c2 << 4) | checksum

    print(f"address: 0x{esphome_addr:04X}, command: 0x{esphome_cmd:X}") # Still working on it...





def rca_raw():
    def reverse_8bits(val):
        return int('{:08b}'.format(val)[::-1], 2)

    addr = int(entry['address'].split()[0], 16)
    cmd = int(entry['command'].split()[0], 16)

    inv_cmd = ~cmd & 0xFF  # 0xB8


    addr_rev = reverse_8bits(addr)
    cmd_rev = reverse_8bits(cmd)
    inv_rev = reverse_8bits(inv_cmd)
    payload = (addr_rev << 16) | (cmd_rev << 8) | inv_rev


    raw_code = [4000, -4000]


    for i in range(23, -1, -1):
        bit = (payload >> i) & 1
        raw_code.append(500)
        if bit == 1:
            raw_code.append(-2000)
        else:
            raw_code.append(-1000)

    # Lead-out
    raw_code.append(500)
    raw_code.append(-10000)





    writer = f"""
- platform: template
  name: "{entry['name']}"
  on_press:
    - remote_transmitter.transmit_raw:
        carrier_frequency: {56}kHz
        code: {raw_code}
    """
    with open("yaml/" + dafile +".yaml", "a") as file:
        file.write(writer)

# VARIABLES

fileis = 'sony' # ONLY IF RUN manually, i.e. not through flask server
dafile = os.getenv('DAFILE', fileis)
if os.path.isfile("yaml/" + dafile + ".yaml"):
    os.remove("yaml/" + dafile + ".yaml")

ir_data = parser("input/" + dafile + '.ir')

for entry in ir_data:
    if entry['type'] == 'raw':
        raw_raw()  # check
    elif entry['type'] == 'parsed':
        if entry['protocol'] == 'NEC':
            nec_nec()  # checkc
        elif entry['protocol'] == 'NECext':
            necext_nec()  # checkc
        elif entry['protocol'] == 'NEC42':
            nec42_pronto()  # checkc
        elif entry['protocol'] == 'NEC42ext':
            nec42ext_pronto()  # NO CLUE - LITERALLY CAN'T TEST IT, NOT EVEN FLIPPER ZERO'S REPO HAS ANY EXAMPLES OF IT?? classic variation of an obscure variation
        elif entry['protocol'] == 'Samsung32':
            samsung32_samsung()  # check
        elif entry['protocol'] == 'RC5': #<------------------------.
            rc5_rc5()  # check             #                       |
        elif entry['protocol'] == 'RC6':   #                       |
            rc6_rc6()  # check             #                       |
        elif entry['protocol'] == 'RC5X':  #                      .^.
            rc5x_rc5()  # LIKE REALLY, Marantz practically treats them as the same thing :/
        elif entry['protocol'] == 'SIRC':
            sirc_sony()  # check
        elif entry['protocol'] == 'SIRC15':
            sirc_sony()  # check
        elif entry['protocol'] == 'SIRC20':
            sirc_sony()  # WHEW, almost forgot that the address can span 2 bytes but check
        elif entry['protocol'] == 'Kaseikyo':
            kaseikyo_panasonic()  # OH DEAR
        elif entry['protocol'] == 'RCA':
            rca_raw()  # uhhhh works sometimes?