# Scale Test Results

## Test Date: 2025-12-17

### Scale Connection Test Results

**Configurations Tested:**
1. 1200 baud, 8N1 - ✗ Failed (received 92 bytes)
2. 2400 baud, 8N1 - ✗ Failed (received 121 bytes)
3. 4800 baud, 8N1 - ✗ Failed (received 188 bytes)
4. 9600 baud, 8N1 - ✗ Failed (received 212 bytes)
5. **1200 baud, 7E1 - ✓ VALID DATA FOUND** (received 90 bytes)
6. 2400 baud, 7E1 - ✗ Failed (received 117 bytes)
7. 9600 baud, 7E1 - ✗ Failed (received 213 bytes)

### Winning Configuration: **1200 baud, 7E1**

**Raw Data Pattern:**
```
0x02 0x28 0x30 0x20 0x20 0x20 0x32 0x39 0x39 0x30 0x20 0x20 0x20 0x20 0x20 0x30 0x0d 0x0a
```

**Decoded as ASCII:**
```
STX ( 0    2990     0 CR LF
 |   |  |    |       | |  |
 |   |  |    |       | |  +-- Line Feed (0x0A)
 |   |  |    |       | +----- Carriage Return (0x0D)
 |   |  |    |       +------- Reserved/Decimal info
 |   |  |    +--------------- Weight digits: "2990" (grams)
 |   |  +-------------------- Status: '0' = stable
 |   +----------------------- Protocol marker: '('
 +--------------------------- Start of Text (0x02)
```

### Protocol Analysis

**Protocol Type:** STX (Start of Text) with CR/LF termination
**Frame Length:** 18 bytes
**Baud Rate:** 1200
**Data Format:** 7 data bits, Even parity, 1 stop bit (7E1)
**Frame Delimiter:** CR LF (0x0D 0x0A)

**Frame Structure:**
- Byte 0: 0x02 (STX - Start of Text)
- Byte 1: 0x28 ('(' - Protocol marker)
- Byte 2: Status character ('0' = stable, '8' = unstable)
- Bytes 3-10: Weight digits (ASCII, space-padded)
- Bytes 11-15: Reserved/padding
- Bytes 16-17: CR LF terminator

**Weight Interpretation:**
- Raw value: "2990"
- Unit: Grams (needs conversion to kg)
- Converted: 2.990 kg

### Next Steps

1. Update decoder to handle STX protocol (1200 baud, 7E1)
2. Implement CR/LF frame detection
3. Parse ASCII weight digits
4. Convert grams to kilograms
5. Detect stable vs unstable status from byte 2
