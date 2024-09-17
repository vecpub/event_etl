SELECT * FROM (
    SELECT * FROM {{ref('stg_event')}}
    UNION
    SELECT * FROM event_supplemental) e