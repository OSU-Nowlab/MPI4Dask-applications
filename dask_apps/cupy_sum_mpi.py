"""
This is the sum of cuPy array and its transpose application. It has been 
modified to work for the MVAPICH2-based (http://mvapich.cse.ohio-state.edu) 
communication backend for the Dask Distributed library using the 
dask-mpi package.

"""
import os
#adjust as per compute system
GPUS_PER_NODE      =   1    # number of GPUs in the system
RUNS               =  20    # repititions for the benchmark
DASK_INTERFACE     = 'ib0'  # interface to use for communication
DASK_PROTOCOL      = 'mpi'  # protocol for Dask Distributed. Options include ['mpi', 'tcp']
THREADS_PER_NODE   =  8    # number of threads per node.

rank = os.environ['MV2_COMM_WORLD_LOCAL_RANK']
device_id = int(rank) % GPUS_PER_NODE
os.environ["CUDA_VISIBLE_DEVICES"]=str(device_id)

import mpi4py
from mpi4py import MPI
import mpi4py.rc
mpi4py.rc.threads = True
from dask_mpi import initialize

import os
import asyncio
from collections import defaultdict
from time import perf_counter as clock

import dask.array as da
from dask.distributed import Client, performance_report, wait
from dask.utils import format_bytes, format_time, parse_bytes

import cupy
import numpy
import time
import sys
import logging

logger = logging.getLogger(__name__)


async def run():
    async with Client(asynchronous=True) as client:

        print(client)

        scheduler_workers = await client.run_on_scheduler(get_scheduler_workers)

        took_list = []

        for i in range(RUNS):
            start = time.time()
            rs = da.random.RandomState(RandomState=cupy.random.RandomState)
            a = rs.normal(100, 1, (int(10000), int(10000)), \
                          chunks=(int(5000), int(5000)))
            x = a + a.T

            xx = await client.compute(x)

            duration = time.time() - start
            took_list.append( (duration, a.npartitions) )
            print("Time for iteration", i, ":", duration)
            sys.stdout.flush()

        sums = []

        for (took, npartitions) in took_list:
            sums.append(took)  
            t = format_time(took)
            t += " " * (11 - len(t))
        
        print ("Average Wall-clock Time: ", format_time(sum(sums)/len(sums)))

        # Collect, aggregate, and print peer-to-peer bandwidths
        incoming_logs = await client.run(
            lambda dask_worker: dask_worker.incoming_transfer_log
        )

        outgoing_logs = await client.run(
            lambda dask_worker: dask_worker.outgoing_transfer_log
        )


def get_scheduler_workers(dask_scheduler=None):
    return dask_scheduler.workers

if __name__ == "__main__":
    # Schedule, client, workers will all call this function
    initialize(
        interface=DASK_INTERFACE,
        protocol=DASK_PROTOCOL,
        nthreads=8,
        comm=MPI.COMM_WORLD,
        local_directory=os.environ.get("TMPDIR", None)
    )

    time.sleep(5)

    asyncio.run(run())
