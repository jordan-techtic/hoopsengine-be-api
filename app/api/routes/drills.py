PATCH: In get_drill_detail decorator, change response_model=DrillDetailResponse to response_model=DrillDetailResponse | PlayerDrillDetailResponse. Add to responses dict:
403: openapi_error_examples(
    'Player cannot access drill or caller lacks permission',
    examples={
        'drill_forbidden': {
            'code': 'FORBIDDEN',
            'message': 'You do not have permission to access this drill',
            'details': [{'field': 'drill_id', 'message': 'You do not have permission to access this drill'}],
        },
    },
),
Expand description to list player response fields: id, drill_id, name, timer (MM:SS elapsed), status, progress (0-100), time_remaining, phone.