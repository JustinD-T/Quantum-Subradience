import gpib

if __name__ == '__main__':

    device = gpib.find('GPIB0::1::INSTR')    
    gpib.write(device,"*IDN?")
    result = gpib.read(device,25)
    print(result)