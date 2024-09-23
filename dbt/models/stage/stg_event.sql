with tm_source as (
select distinct 
	event.name as name,
    'ticketmaster' as source,
    md5(concat(event.name, '|' ,(event.dates->'start'->>'dateTime')::timestamptz )) as key,
    (event.dates->'start'->>'dateTime')::timestamptz as start_datetime,
    event.id as external_id,
    event.url as ticket_url,
    event.dates->'status'->>'code' as ticket_status,
    event._embedded->'venues'->0->>'id' as source_place_id,
    md5(concat(
    	event._embedded->'venues'->0->>'name', '|' , event._embedded->'venues'->0->'state'->>'stateCode' 
    )) as place_key,
	event.classifications->0->'segment'->>'name' as segment,
	event.classifications->0->'genre'->>'name' as genre,
	event.classifications->0->'subGenre'->>'name' as sub_genre,
	event.price_ranges->0->>'min' as price_min,
	event.price_ranges->0->>'max' as price_max,
	img.image_url
from pipeline_ticketmaster.stg_ticketmaster event
left join
(
SELECT sub.id, sub.image_url
FROM (
    SELECT
        event_img.id,
        img->>'url' AS image_url,
        (img->>'width')::int AS width,
        ROW_NUMBER() OVER (PARTITION BY event_img.id ORDER BY (img->>'width')::int) AS rn
    FROM pipeline_ticketmaster.stg_ticketmaster event_img,
    LATERAL jsonb_array_elements(event_img.images) AS img
    WHERE (img->>'width')::int > 300
    order by (img->>'width')::int
) AS sub
WHERE sub.rn = 1
) img
on img.id = event.id
)
select * from tm_source