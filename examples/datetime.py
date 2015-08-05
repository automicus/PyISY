#!/usr/local/bin/python3.3
#

import yaml

from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler

stream = open('config.yaml', 'r') 
config = yaml.load(stream)
print(config['isy_host'])

def second_function():
    print('other_funciton: The time is: %s' % datetime.now())

def minute_function():
    print('minute_function: The minute is: %s' % datetime.now().minute)

def hour_function():
    print('hour_function: The hour is: %s' % datetime.now().hour);

def day_function():
    print('day_function: It is a new day!  The time is: %s' % datetime.now());

sched = BlockingScheduler()

# Schedules second_function to be run at the change of each second.
#sched.add_job(second_function, 'cron', second='0-59')

# Schedules minute_function to be run at the change of each minute.
sched.add_job(minute_function, 'cron', second='0')

# Schedules hour_function to be run at the change of each hour.
sched.add_job(hour_function, 'cron', minute='0', second='0')

# Schedules day_function to be run at the start of each day.
sched.add_job(day_function, 'cron', minute='0', second='0', hour='0')

sched.start()
