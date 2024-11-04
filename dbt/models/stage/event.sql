SELECT * FROM (
    SELECT distinct on (key) * FROM {{ref('stg_event')}}
    UNION
    SELECT * FROM event_supplemental) e