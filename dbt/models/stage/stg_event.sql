with tm_source as (
select distinct 
	event.name as name,
    'ticketmaster' as source,
    md5(concat(event.name, '|' ,dates__start__local_date)) as key,
    dates__start__date_time as start_datetime,
    event.id as external_id,
    event.url as ticket_url,
    dates__status__code as ticket_status,
    --venue.name as place_name,
    venue.id as source_place_id,
    md5(concat(venue.name, '|' ,venue.city__name, venue.state__state_code)) as place_key,
    classification.segment__name as segment_name,
    classification.genre__name as genre_name,
    classification.sub_genre__name as sub_genre_name

from pl_ticketmaster.stg_ticketmaster event
left join pl_ticketmaster.stg_ticketmaster___embedded__venues venue on event._dlt_id = venue._dlt_parent_id
left join pl_ticketmaster.stg_ticketmaster__classifications classification on event._dlt_id = classification._dlt_parent_id

--order by 1
)
select * from tm_source