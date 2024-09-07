select * from {{ref('stg_place')}}
where row_hash not in (select * from public.place_is_deleted)