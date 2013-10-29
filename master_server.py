#!/usr/bin/python

import globals
import time
import sys
import os
from datetime import datetime, timedelta
import utility
import signal
import getopt
import glob


def signal_handler(signal, frame):
    """


    @rtype : object
    @param signal:
    @param frame:
    """
    unload()
    sys.exit(0)


def unload():
    """



    @rtype : object
    """
    print "\nunloading"
    cursor = _db.cursor()
    cursor.execute("DELETE FROM Servers WHERE ServerType = 'Master' AND UUID = '%s'" % (str(_uuid)))
    _db.close()


def register_master_server(uuid):
    """


    @rtype : boolean
    @param uuid:
    @return:
    """
    timestamp = datetime.now()

    cursor = _db.cursor()
    cursor.execute("SELECT LocalIP, PublicIP, LastSeen, UUID, ServerType FROM Servers WHERE ServerType = 'Master'")
    results = cursor.fetchone()

    if results is None:
        cursor.execute(
            "INSERT INTO Servers(LocalIP, PublicIP, ServerType, LastSeen, UUID, State) VALUES('%s','%s','%s','%s','%s','%s')" % (
                _localip, _publicip, 'Master', timestamp, uuid, 0))
        print "Server successfully registered as the Master Server running on [L}%s / [P}%s on %s" % (
            _localip, _publicip, timestamp)
    else:
        if results[0] == _localip and results[1] == _publicip and str(results[3]) == str(uuid):
            print "Registering Master Server %s heartbeat at %s" % (_uuid, timestamp)
            cursor.execute(
                "UPDATE Servers SET LastSeen = '%s' WHERE LocalIP = '%s' AND PublicIP = '%s' AND ServerType = 'Master' AND UUID = '%s'" % (
                    timestamp, _localip, _publicip, uuid))
        elif (timestamp - results[2]) > timedelta(seconds=30):
            print "The Master Server running on [L]%s / [P]%s but heartbeat has not been detected for more than 30 seconds." % (
                results[0], results[1])
            print "Registering this server as the Master Server"
            cursor.execute("DELETE FROM Servers WHERE ServerType = 'Master'")
            register_master_server(uuid)
        else:
            print "A Master Server is actively running on [L]%s / [P]%s. Last heartbeat was seen on %s" % (
                results[0], results[1], results[2])
            sys.exit(1)

    _db.commit()
    return True


def remove_stale_slave_servers():
    """



    @rtype : object
    @return:
    """
    timestamp = datetime.now()
    cursor = _db.cursor()
    cursor.execute("SELECT LastSeen, UUID, ServerType FROM Servers WHERE ServerType = 'Slave'")
    results = cursor.fetchall()
    for row in results:
        if (timestamp - row[0]) > timedelta(seconds=60):
            print "Removing stale slave server %s" % row[1]
            cursor.execute("DELETE FROM Servers WHERE ServerType = 'Slave' AND UUID = '%s'" % (str(row[1])))
            cursor.execute("DELETE FROM Connectivity WHERE SlaveServerUUID = '%s'" % (str(row[1])))
    return True


def remove_stale_connectivity_entries():
    """



    @rtype : boolean
    """
    deletecursor = _db.cursor()
    connectivitycursor = _db.cursor()
    connectivitycursor.execute("SELECT StorageUUID FROM Connectivity")
    connectivityresults = connectivitycursor.fetchall()
    for connectivityrow in connectivityresults:
        storagecursor = _db.cursor()
        storagecursor.execute("SELECT UUID FROM Storage")
        storageresults = storagecursor.fetchall()
        keep = 0
        for storagerow in storageresults:
            if connectivityrow[0] == storagerow[0]:
                keep = 1
        if keep == 0:
            print "Removing stale connectivity entry with StorageUUID", connectivityrow[0]
            deletecursor.execute("DELETE FROM Connectivity WHERE StorageUUID = '%s'" % connectivityrow[0])
    return True


def remove_stale_storage_servers():
    """



    @rtype : object
    @return:
    """
    timestamp = datetime.now()
    cursor = _db.cursor()
    cursor.execute("SELECT LastSeen, UUID, ServerType FROM Servers WHERE ServerType = 'Storage'")
    results = cursor.fetchall()
    for row in results:
        if (timestamp - row[0]) > timedelta(seconds=30):
            print "Removing stale storage server %s" % row[1]
            cursor2 = _db.cursor()
            cursor2.execute("SELECT UUID, ServerUUID FROM Storage WHERE ServerUUID = '%s'" % str(row[1]))
            results2 = cursor2.fetchall()
            for row2 in results2:
                cursor.execute("DELETE FROM Connectivity WHERE StorageUUID = '%s'" % (str(row2[0])))
            cursor.execute("DELETE FROM Storage WHERE ServerUUID = '%s'" % (str(row[1])))
            cursor.execute("DELETE FROM Servers WHERE ServerType = 'Storage' AND UUID = '%s'" % (str(row[1])))
    return True


def remove_orphaned_storage_confirmation_files():
    """


    @rtype : boolean
    @return:
    """
    storagecursor = _db.cursor()
    servercursor = _db.cursor()
    storagecursor.execute("SELECT UUID FROM Storage")
    storageresults = storagecursor.fetchall()
    for storagerow in storageresults:
        storagepath = utility.get_storage_nfs_folder_path(storagerow[0])
        todelete = storagepath + "*-*-*-*-*"
        for file in glob.glob(todelete):
            servercursor.execute("SELECT UUID FROM Servers")
            serverresults = servercursor.fetchall()
            delete = 1
            for serverrow in serverresults:
                serveruuidfile = storagepath + serverrow[0]
                if serveruuidfile == file:
                    delete = 0
            storageuuidfile = storagepath + storagerow[0]
            if storageuuidfile == file:
                delete = 0
            if delete == 1:
                print "Removing orphaned storage confirmation file", file
                os.remove(file)
    return True


def fetch_jobs():
    """



    @rtype : boolean
    """
    jobcursor = _db.cursor()
    jobcursor.execute(
        "SELECT UUID, JobType, JobSubType, Command, CommandOptions, JobInput, JobOutput, Assigned, State, AssignedServerUUID, StorageUUID, Priority, Dependencies, MasterUUID, Progress, ResultValue1, ResultValue2, JobOptions FROM Jobs")
    jobresults = jobcursor.fetchall()

    for jobrow in jobresults:
        jobuuid = jobrow[0]
        jobtype = jobrow[1]
        jobsubtype = jobrow[2]
        command = jobrow[3]
        commandoptions = jobrow[4]
        jobinput = jobrow[5]
        joboutput = jobrow[6]
        jobassigned = jobrow[7]
        jobstate = jobrow[8]
        jobassignedserveruuid = jobrow[9]
        storageuuid = jobrow[10]
        jobpriority = jobrow[11]
        jobdependencies = jobrow[12]
        masteruuid = jobrow[13]
        jobprogress = jobrow[14]
        resultsvalue1 = jobrow[15]
        resultsvalue2 = jobrow[16]
        joboptions = jobrow[17]

        # deal with master jobs
        if jobtype == "Master":
            if jobsubtype == "transcode":

                if jobstate == 0:
                    updatecursor = _db.cursor()
                    updatecursor.execute("UPDATE Jobs SET State='%s' WHERE UUID='%s'" % (1, jobuuid))
                    detect_frames_job_uuid = utility.get_uuid()
                    utility.submit_job(detect_frames_job_uuid, "Slave", "detect frames", "ffmpeg -y -i %s %s %s", commandoptions, jobinput, joboutput, "", jobuuid, joboptions)

                if jobstate == 1:
                    child_jobs = 0
                    childcursor = _db.cursor()
                    childcursor.execute("SELECT JobSubType, MasterUUID, State FROM Jobs WHERE MasterUUID='%s'" % (jobuuid))
                    childresults = childcursor.fetchall()
                    for row in childresults:
                        if row[0] == "detect frames":
                            child_jobs += 1
                        elif row[2] < 2:
                            child_jobs += 1

                    if child_jobs == 0:
                        childcursor.execute("DELETE FROM Jobs WHERE MasterUUID='%s' AND State='%s'" % (jobuuid, 2))
                        childcursor.execute("UPDATE Jobs SET State='%s' WHERE UUID='%s'" % (2, jobuuid))

                if jobstate == 2:
                    if joboptions == "confirm_framecount":
                            if resultsvalue1 < resultsvalue2:
                                print "Transcoded file has", int(resultsvalue2) - int(resultsvalue1), "more frames than the source."
                            if resultsvalue1 > resultsvalue2:
                                print "Transcoded file has", int(resultsvalue1) - int(resultsvalue2), "less frames than the source."
                            if resultsvalue1 == resultsvalue2:
                                print "Source and Transcoded file have the same number of frames:", resultsvalue1
                    deletecursor = _db.cursor()
                    deletecursor.execute("DELETE FROM Jobs WHERE UUID='%s'" % jobuuid)

        # if detect frames job is done, initiate split-stitch transcode process
        if jobtype == "Slave" and jobsubtype == "detect frames" and jobstate == 2:
            deletecursor = _db.cursor()
            deletecursor.execute("DELETE FROM Jobs WHERE UUID = '%s'" % jobuuid)

            mux_dependencies = ""

            # create audio demux job
            demuxjob_uuid = utility.get_uuid()
            audio_demuxed_filetype = ".wav"
            audio_demuxed_file = joboutput + "_audio" + audio_demuxed_filetype
            utility.submit_job(demuxjob_uuid, "Slave", "audio demux", "ffmpeg -y %s -i %s -vn %s", "-flags:a +global_header", jobinput, audio_demuxed_file,
            mux_dependencies, masteruuid, "")
            mux_dependencies += str(demuxjob_uuid)

            merge_dependencies, merge_textfile = split_transcode_job(jobuuid, command, commandoptions, jobinput, joboutput, storageuuid, masteruuid, resultsvalue1, resultsvalue2)

            # create merge job
            mergejob_uuid = utility.get_uuid()
            outfilename, outfileextension = os.path.splitext(joboutput)
            joboutput_video = joboutput + "_video" + outfileextension
            utility.submit_job(mergejob_uuid, "Storage", "video merge", "ffmpeg -y %s -f concat -i %s -c copy %s", " ", merge_textfile, joboutput_video,
                       merge_dependencies, masteruuid, "")
            if mux_dependencies[-1:] != ",":
                mux_dependencies += ","
            mux_dependencies += str(mergejob_uuid)

            # create audio/video mux job
            muxinput = joboutput_video + "," + audio_demuxed_file
            muxjob_uuid = utility.get_uuid()
            utility.submit_job(muxjob_uuid, "Storage", "a/v mux", "ffmpeg -y %s %s -vcodec copy %s", " ", muxinput, joboutput, mux_dependencies, masteruuid, "")

            if utility.find_job_options_for_job(masteruuid) == "confirm_framecount":
                utility.submit_job("", "Slave", "count frames", "ffprobe -show_frames %s | grep -c media_type=video", "input", jobinput, " ", muxjob_uuid, masteruuid, "")
                utility.submit_job("", "Slave", "count frames", "ffprobe -show_frames %s | grep -c media_type=video", "output", joboutput, " ", muxjob_uuid, masteruuid, "")

    return True


def split_transcode_job(jobuuid, command, commandoptions, jobinput, joboutput, storageuuid, masteruuid, resultsvalue1, resultsvalue2):
    """



    @rtype : boolean
    """
    merge_dependencies = ""
    keyframes = resultsvalue1.split(",")
    keyframes_diff = resultsvalue2.split(",")

    # determine how many active slaves exist
    num_slaves = utility.number_of_registered_slaves()
    # determine length of each sub-clip

    storage_nfs_path = utility.get_storage_nfs_folder_path(storageuuid)

    outfilename, outfileextension = os.path.splitext(joboutput)
    merge_textfile = joboutput + "_mergeinput.txt"
    merge_textfile_fullpath = storage_nfs_path + joboutput + "_mergeinput.txt"
    keyframe_index = 0

    # create transcode jobs for each sub-clip
    for num in range(0, num_slaves):
        print "Splitting Job ", jobuuid, " into part ", num

        # if last keyframe, dont specify time period
        if keyframes_diff[keyframe_index] == "-1":
            ffmpeg_startstop = "-an -ss %f -y" % float(keyframes[keyframe_index])
        else:
            ffmpeg_startstop = "-an -ss %f -t %f" % (float(keyframes[keyframe_index]), float(keyframes_diff[keyframe_index]))

        ffmpeg_startstop += commandoptions

        jobuuid = utility.submit_job("", "Slave", "transcode", "ffmpeg -y l-flags:v +global_header -i %s %s %s", ffmpeg_startstop, jobinput,
                             joboutput + "_part" + str(num) + outfileextension, "", masteruuid, "")
        keyframe_index += 1
        merge_dependencies += str(jobuuid)
        merge_dependencies += ","
        # write the merge textfile for ffmpeg concat
        with open(merge_textfile_fullpath, "a") as mergefile:
            mergefile.write("file '" + storage_nfs_path + joboutput + "_part" + str(num) + outfileextension + "'\n")
            mergefile.close()

    if merge_dependencies[-1:] == ",":
        merge_dependencies = merge_dependencies[:-1]

    return merge_dependencies, merge_textfile




def cleanup_tasks():
    remove_stale_slave_servers()
    remove_stale_storage_servers()
    remove_stale_connectivity_entries()
    remove_orphaned_storage_confirmation_files()
    return True


def usage():
    """



    @rtype : none
    """
    print "\nUsage: master_server.py: [options]"
    print "-h / --help : help"
    print "-d [address:{port}] / --database [ip address:{port}] : specify the fflock database\n"


def parse_cmd(argv):
    """


    @rtype : none
    @param argv:
    """

    try:
        opts, args = getopt.getopt(argv, "hd:", ["help", "database="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        if opt in ("-d", "--database"):
            globals.DATABASE_HOST = arg.split(':', 1)[0]
            globals.DATABASE_PORT = arg.split(':', 1)[-1]
            if globals.DATABASE_PORT == globals.DATABASE_HOST:
                globals.DATABASE_PORT = 3306
    return True


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    _uuid = utility.get_uuid()
    _localip = utility.local_ip_address()
    _publicip = utility.public_ip_address()

    parse_cmd(sys.argv[1:])
    _db = utility.dbconnect()

    while True:
        register_master_server(_uuid)
        fetch_jobs()
        cleanup_tasks()
        time.sleep(2)