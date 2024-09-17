SELECT * FROM (
    SELECT * FROM {{ref('stg_place')}}
    UNION
    SELECT *, md5(place_supplemental::text)::uuid as row_hash FROM place_supplemental) p
where row_hash not in (select * from place_is_deleted)