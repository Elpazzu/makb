#==================================================
# Spark Python Script Kafka => HBase
#==================================================

from pyspark import SparkContext, SparkConf
from pyspark.streaming import StreamingContext
from pyspark.streaming.kafka import *
from pyspark_ext import *
import happybase

#==================================================
# Initialization / Control
#==================================================

appName = "Kafka_to_HBase"
config = SparkConf().setAppName(appName)  

props = []
props.append(("spark.rememberDuration", "10"))
props.append(("spark.batchDuration", "10"))
props.append(("spark.eventLog.enabled", "true"))
props.append(("spark.streaming.timeout", "30"))
props.append(("spark.ui.enabled", "true"))

config = config.setAll(props)

sc = SparkContext(conf=config)  
ssc = StreamingContext(sc, int(config.get("spark.batchDuration")))

#==================================================
# Main application execution function
#==================================================

def runApplication(ssc, config):
  ssc.start()
  if config.get("spark.streaming.timeout") == '':
    ssc.awaitTermination()
  else:
    stopped = ssc.awaitTerminationOrTimeout(int(config.get("spark.streaming.timeout")))
  if not stopped :
    print("Stopping streaming context after timeout...")
    ssc.stop(True)
    print("Streaming context stopped.")

#==================================================
# Output application details
#==================================================

print
print ( "APPNAME:" + config.get( "spark.app.name" ))
print ( "APPID:" +   sc.applicationId)
print ( "VERSION:" + sc.version)
print

#==================================================
# Begin of Mapping Logic
#==================================================

hbase_table = 'clicks'
hconn = happybase.Connection('kafkademo')  
ctable = hconn.table(hbase_table)

topic = ["/users-stream:clicks"]
k_params = {"key.deserializer" : "org.apache.kafka.common.serialization.StringDeserializer" \
	,"value.deserializer" : "org.apache.kafka.common.serialization.StringDeserializer" \
	,"zookeeper.connect" : "maprdemo:5181"
	,"metadata.broker.list" : "this.will.be.ignored:9092"
	,"session.timeout.ms" : "45"
	,"group.id" : "Kafka_MapR-Streams_to_HBase"}

def SaveToHBase(rdd):
    print("=====Pull from Stream=====")
    if not rdd.isEmpty():
        print("=some records=")
        for line in rdd.collect():
            ctable.put(('click' + line.serial_id), { \
            b'clickinfo:studentid': (line.studentid), \
            b'clickinfo:url': (line.url), \
            b'clickinfo:time': (line.time), \
            b'iteminfo:itemtype': (line.itemtype), \
            b'iteminfo:quantity': (line.quantity)})

kds = KafkaUtils.createDirectStream(ssc, topic, k_params, fromOffsets=None)

parsed = kds.filter(lambda x: x != None and len(x) > 0 )
parsed = parsed.map(lambda x: x[1])
parsed = parsed.map(lambda rec: rec.split(","))
parsed = parsed.filter(lambda x: x != None and len(x) == 6 )
parsed = parsed.map(lambda data:Row(serial_id=getValue(str,data[0]), \
		studentid=getValue(str,data[1]), \
		url=getValue(str,data[2]), \
		time=getValue(str,data[3]), \
		itemtype=getValue(str,data[4]), \
		quantity=getValue(str,data[5])))

parsed.foreachRDD(SaveToHBase)

#===================================================
# Start application
#===================================================

runApplication(ssc, config)

print
print ("SUCCESS")
print

#===================================================
# Test/debug the code 
#===================================================

./spark-submit --master yarn-client \
--py-files ~/kafka-hbase/pyspark_ext.py \
--deploy-mode client --executor-memory 1G --verbose --driver-memory 512M \
--executor-cores 1 --driver-cores 1 --num-executors 2 --queue default \
~/kafka-hbase/Kafka-HBase.py
