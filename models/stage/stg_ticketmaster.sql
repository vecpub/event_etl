--drop type event_row_type;
--create type event_row_type as (name text, id text, type text, dates jsonb, _embedded jsonb, classifications jsonb);

select
	batch_id,
	json_cols.name,
	json_cols.type,
	json_cols.id as source_id,
	json_cols._embedded->'venues'->0->>'name' as venue_name,
	json_cols._embedded->'venues'->0->>'id' as source_venue_id,
	json_cols._embedded->'venues'->0->'location'->>'latitude' as venue_lat,
	json_cols._embedded->'venues'->0->'location'->>'longitude' as venue_lon,
	json_cols.classifications->0->'genre'->>'name' as genre,
	json_cols.classifications->0->'subGenre'->>'name' as sub_genre,
	(json_cols.dates->'start'->>'dateTime')::timestamp as start_time_utc,
	(json_cols.dates->'start'->>'dateTime')::timestamptz AT TIME ZONE 'America/New_York' as start_time_local,
	json_cols.dates->>'timezone' as event_timezone

from event_staging,
	jsonb_populate_recordset(null::event_row_type, json_data->'_embedded'->'events') as json_cols