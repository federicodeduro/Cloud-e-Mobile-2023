###### TEDx-Load-Aggregate-Model
######

import sys
import json
import pyspark
from pyspark.sql.functions import col, collect_list, array_join, struct, length

from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job




##### FROM FILES
tedx_dataset_path ="s3://unibg-2023-dati-tedx-sg/tedx_dataset.csv"

###### READ PARAMETERS
args = getResolvedOptions(sys.argv, ['JOB_NAME'])

##### START JOB CONTEXT AND JOB
sc = SparkContext()


glueContext = GlueContext(sc)
spark = glueContext.spark_session


    
job = Job(glueContext)
job.init(args['JOB_NAME'], args)


#### READ INPUT FILES TO CREATE AN INPUT DATASET
tedx_dataset = spark.read \
    .option("header","true") \
    .option("quote", "\"") \
    .option("escape", "\"") \
    .csv(tedx_dataset_path)
    
tedx_dataset.printSchema()


#### FILTER ITEMS WITH NULL POSTING KEY
count_items = tedx_dataset.count()
count_items_null = tedx_dataset.filter("idx is not null").count()
tedx_dataset = tedx_dataset.filter("idx NOT LIKE '%[ ]%'")
count_correct_id = tedx_dataset.count()
tedx_dataset = tedx_dataset.filter(length(col('idx')) == 32)
count_idx_length = tedx_dataset.count()


print(f"Number of items from RAW DATA {count_items}")
print(f"Number of items from RAW DATA with NOT NULL KEY {count_items_null}")



## READ TAGS DATASET
tags_dataset_path = "s3://unibg-2023-dati-tedx-sg/tags_dataset.csv"
tags_dataset = spark.read.option("header","true").csv(tags_dataset_path)



# CREATE THE AGGREGATE MODEL, ADD TAGS TO TEDX_DATASET
tags_dataset_agg = tags_dataset.groupBy(col("idx").alias("idx_ref")).agg(collect_list("tag").alias("tags"))
tags_dataset_agg.printSchema()
tedx_dataset_agg = tedx_dataset.join(tags_dataset_agg, tedx_dataset.idx == tags_dataset_agg.idx_ref, "left") \
    .drop("idx_ref") \
    .select(col("idx").alias("_id"), col("*")) \
    .drop("idx") \

tedx_dataset_agg.printSchema()

##### READ WATCH NEXT DATASET
watch_next_dataset_path = "s3://unibg-2023-dati-tedx-sg/watch_next_dataset.csv"
watch_next_dataset = spark.read.option("header","true").csv(watch_next_dataset_path)


##### CLEAN WATCH NEXT DATASET(NULL IDX AND DUPLICATES)
watch_next_dataset = watch_next_dataset.dropDuplicates()

##### CREATE THE AGGREGATE MODEL, ADD TAGS TO TEDX_DATASET
tags_dataset_agg = tags_dataset.groupBy(col("idx").alias("idx_ref")).agg(collect_list("tag").alias("tags"))
tags_dataset_agg.printSchema()
tedx_dataset_agg_1 = tedx_dataset.join(tags_dataset_agg, tedx_dataset.idx == tags_dataset_agg.idx_ref, "left") \
    .drop("idx_ref") \
    .select(col("idx").alias("_id"), col("*")) \

##### CREATE THE AGGREGATE MODEL, ADD WATCH_NEXT TO TEDX_DATASET
watch_next_dataset_agg_a  = watch_next_dataset.groupBy(col("watch_next_idx")).agg({'watch_next_idx':'count'}).withColumnRenamed("count(watch_next_idx)", "n_wn")
watch_next_dataset_agg_b = watch_next_dataset.groupBy(col("idx").alias("idx_ref")).agg(collect_list("watch_next_idx").alias("watch_next"))
watch_next_dataset_agg_2 = watch_next_dataset_agg_a.join(watch_next_dataset_agg_b, watch_next_dataset_agg_a.watch_next_idx == watch_next_dataset_agg_b.idx_ref, "left")\
    .drop("watch_next_idx") \


tedx_dataset_agg_3 = tedx_dataset_agg_1.join(watch_next_dataset_agg_2, tedx_dataset_agg_1.idx == watch_next_dataset_agg_2.idx_ref, "left")\
    .drop("idx_ref") \
    .select(col("idx").alias("_id"), col("*")) \
    .drop("idx") \




mongo_uri = "mongodb+srv://user123:1234@mycluster.8qlyyyv.mongodb.net"

print(mongo_uri)

write_mongo_options = {
    "uri": mongo_uri,
    "database": "unibg_tedx_2023",
    "collection": "tedx_data",
    "ssl": "true",
    "ssl.domain_match": "false"}
from awsglue.dynamicframe import DynamicFrame
tedx_dataset_dynamic_frame = DynamicFrame.fromDF(tedx_dataset_agg_3, glueContext, "nested")

glueContext.write_dynamic_frame.from_options(tedx_dataset_dynamic_frame, connection_type="mongodb", connection_options=write_mongo_options)