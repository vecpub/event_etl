with tm_source as (
select distinct 
	event._embedded->'venues'->0->>'name' as name, 
    'ticketmaster' as source,
    md5(concat(
    	event._embedded->'venues'->0->>'name', '|' , event._embedded->'venues'->0->'state'->>'stateCode' 
    ))::uuid as key,
    event._embedded->'venues'->0->>'id' as external_id,
    event._embedded->'venues'->0->'location'->>'latitude' as lat,
    event._embedded->'venues'->0->'location'->>'longitude' as lon,
    event._embedded->'venues'->0->'address'->>'line1' as street,
    event._embedded->'venues'->0->'city'->>'name' as city_name,
    event._embedded->'venues'->0->'state'->>'stateCode' as state_code,
    event._embedded->'venues'->0->>'postalCode' as postal_code,
    event._embedded->'venues'->0->>'url' as website,
	event._embedded->'venues'->0->'social'->'twitter'->>'handle' as twitter_handle
from pipeline_ticketmaster.stg_ticketmaster event order by 1
)
select *, md5(tm_source::text)::uuid as row_hash from tm_source