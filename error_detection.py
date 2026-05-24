import random
from typing import List, Tuple

def str_to_bits(data):
    bits = []
    for ch in data:
        for b in format(ord(ch),'08b'): bits.append(int(b))
    return bits

def bits_to_str(bits):
    chars=[]
    for i in range(0,len(bits)-len(bits)%8,8):
        chars.append(chr(int(''.join(map(str,bits[i:i+8])),2)))
    return ''.join(chars)

def introduce_errors(bits, rate):
    corrupted=bits.copy(); flipped=[]
    for i in range(len(corrupted)):
        if random.random()<rate: corrupted[i]^=1; flipped.append(i)
    return corrupted, flipped

def _xor(a,b): return [x^y for x,y in zip(a,b)]

class ParityCheck:
    name="Parity Check"; overhead_bits=1
    @staticmethod
    def _p(bits): return sum(bits)%2
    @staticmethod
    def encode(bits): return bits+[ParityCheck._p(bits)]
    @staticmethod
    def detect(bits):
        if len(bits)<1: return False
        return ParityCheck._p(bits[:-1])!=bits[-1]

class Checksum:
    name="Checksum"; overhead_bits=16
    @staticmethod
    def _words(bits):
        p=bits+[0]*((-len(bits))%16)
        return [int(''.join(map(str,p[i:i+16])),2) for i in range(0,len(p),16)]
    @staticmethod
    def _compute(bits):
        t=0
        for w in Checksum._words(bits):
            t+=w
            if t>0xFFFF: t=(t&0xFFFF)+(t>>16)
        return (~t)&0xFFFF
    @staticmethod
    def _i2b(n): return [int(b) for b in format(n&0xFFFF,'016b')]
    @staticmethod
    def encode(bits): return bits+Checksum._i2b(Checksum._compute(bits))
    @staticmethod
    def detect(bits):
        if len(bits)<16: return False
        return Checksum._compute(bits[:-16])!=int(''.join(map(str,bits[-16:])),2)

class CRC:
    name="CRC-16"; overhead_bits=16
    POLY=[1,0,0,0,1,0,0,0,0,0,0,1,0,0,0,0,1]
    @staticmethod
    def _div(dividend,divisor):
        n=len(divisor); cur=list(dividend[:n])
        for i in range(n,len(dividend)+1):
            if cur[0]==1: cur=_xor(cur,divisor)
            cur=cur[1:]
            if i<len(dividend): cur.append(dividend[i])
        return cur
    @staticmethod
    def encode(bits): return bits+CRC._div(bits+[0]*16,CRC.POLY)
    @staticmethod
    def detect(bits):
        if len(bits)<16: return False
        return any(b!=0 for b in CRC._div(bits,CRC.POLY))

TECHNIQUES={"Parity Check":ParityCheck,"Checksum":Checksum,"CRC-16":CRC}
SAMPLE_MESSAGES=["Hello, World!","Network Error Detection","Data Communication Systems",
                 "ABCDEFGHIJKLMNOP","0123456789ABCDEF","The quick brown fox","Error detection test"]

def run_simulation(error_rates, trials=600):
    import random
    results={name:{"error_rates":[],"detection_rates":[],"undetected_rates":[]}
             for name in TECHNIQUES}
    for rate in error_rates:
        for name,tech in TECHNIQUES.items():
            detected=0; total=0
            for _ in range(trials):
                msg=random.choice(SAMPLE_MESSAGES)
                orig=str_to_bits(msg); enc=tech.encode(orig)
                corr,flipped=introduce_errors(enc,rate)
                if not flipped: continue
                total+=1
                if tech.detect(corr): detected+=1
            det=detected/total if total else 0.0
            results[name]["error_rates"].append(round(rate,4))
            results[name]["detection_rates"].append(round(det,6))
            results[name]["undetected_rates"].append(round(1-det,6))
    return results

def simulate_single(message, error_rate):
    orig=str_to_bits(message); output={}
    for name,tech in TECHNIQUES.items():
        enc=tech.encode(orig); corr,flipped=introduce_errors(enc,error_rate)
        detected=tech.detect(corr) if flipped else False
        try: recv=bits_to_str(corr[:len(orig)])
        except: recv="???"
        output[name]={"original_bits":len(orig),"encoded_bits":len(enc),
                      "overhead_bits":tech.overhead_bits,"errors_injected":len(flipped),
                      "error_positions":flipped[:20],"error_detected":detected,
                      "received_msg":recv,"original_msg":message}
    return output