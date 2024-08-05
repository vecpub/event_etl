

with tm_source as (
select distinct name, 
    'ticketmaster' as source,
    md5(concat(name, '|' ,city__name, state__state_code)) as key,
    id as external_id,
    location__latitude as latitude,
    location__longitude as longitude,
    address__line1 as address_line_1,
    address__line2 as address_line_2,
    postal_code,
    city__name as city_name,
    state__state_code as state_code,
country__country_code as country_code,
social__twitter__handle as twitter_handle
from pl_ticketmaster.stg_ticketmaster___embedded__venues order by 1
)
select * from tm_source