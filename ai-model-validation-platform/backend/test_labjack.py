from labjack import ljm
try:
    handle = ljm.openS('T7', 'USB', 'ANY')
    print('Successfully opened LabJack T7!')
    info = ljm.getHandleInfo(handle)
    print(f'Device: {info[0]}, Connection: {info[1]}, Serial: {info[2]}')
    ljm.close(handle)
    print('Hardware connection successful!')
except Exception as e:
    print(f'Failed to connect to hardware: {e}')
    print('This is why the system uses mock mode')
