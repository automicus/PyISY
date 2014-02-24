import time

# CONTROL MODULE TESTS
def_settings = {'nodes': False, 'scenes': False, 'programs': False, 'variables': False, 'environment': False, 'networking': True}

def runTests(isy, settings=def_settings, ISY_NODE_ADDR='1', ISY_SCENE_ADDR='1', ISY_PROG_ADDR='0001', ISY_VAR_ADDR=[1,1], ISY_NET_ADDR=0):
    if settings['nodes']:
        print ' '
        print 'UPDATE NODES'
        isy.nodes.update()

        print ' '
        print 'ISOLATE DEVICES'
        node = isy.nodes[ISY_NODE_ADDR]

        print ' '
        print 'MANIPULATE NODE'
        time.sleep(1)
        print 'TURNING ON NODE'
        node.on()
        print 'NEW VALUE: ' + str(node['status'])
        time.sleep(10)
        print 'TURNING OFF NODE'
        node.off()
        print 'NEW VALUE: ' + str(node['status'])
        time.sleep(10)
        print 'MANUALLY SET VALUE'
        node['status'] = 150
        print 'NEW VALUE: ' + str(node['status'])
        time.sleep(10)

        print ' '
        print 'STARTING UPDATE THREAD'
        print 'CTRL+C TO QUIT'
        isy.auto_update = True
        print 'DEVICE VALUE:'
        try:
            while True:
                print node['status']
                time.sleep(0.5)
        except KeyboardInterrupt:
            isy.auto_update = False
            print ''

    if settings['scenes']:
        print ' '
        print 'ISOLATE DEVICES'
        scene = isy.nodes[ISY_SCENE_ADDR]

        print ' '
        print 'MANIPULATE SCENE'
        time.sleep(1)
        print 'TURNING OFF SCENE'
        scene.off()
        time.sleep(10)
        print 'TURNING ON SCENE'
        scene.on()

    if settings['programs']:
        print ''
        print 'ISOLATE PROGRAM'
        prog = isy.programs[ISY_PROG_ADDR]

        print ''
        print 'RUNNING PROGRAM'
        prog.runThen()

        print ' '
        print 'STARTING UPDATE THREAD'
        print 'CTRL+C TO QUIT'
        isy.auto_update = True
        print 'PROGRAM RUNNING:'
        try:
            while True:
                print prog['running']
                time.sleep(0.5)
        except KeyboardInterrupt:
            isy.auto_update = False
            print ''

    if settings['variables']:
        print ''
        print 'ISOLATE VARIABLE'
        var = isy.variables[ISY_VAR_ADDR[0]][ISY_VAR_ADDR[1]]

        print ''
        print 'CHANGING TO 1'
        var['val'] = 1
        time.sleep(2)

        print 'CHANGING TO 0'
        var['val'] = 0
        time.sleep(2)

        print ' '
        print 'STARTING UPDATE THREAD'
        print 'CTRL+C TO QUIT'
        isy.auto_update = True
        print 'VARIABLE VALUE:'
        try:
            while True:
                print var['val']
                time.sleep(0.5)
        except KeyboardInterrupt:
            isy.auto_update = False
            print ''

    if settings['environment']:
        print ''
        print 'ENVIRONMENT VALUES'
        for param in isy.climate:
            print param + ': ' + str(isy.climate[param]) + ' ' + str(isy.climate.units[param])

    if settings['networking']:
        print ''
        print 'ISOLATE NETWORK COMMAND'
        net = isy.networking[ISY_NET_ADDR]

        print ''
        print 'RUNNING COMMAND'
        net.run()