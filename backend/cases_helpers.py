import datetime


CASE_CATEGORIES = ['非我局管辖', '挂账案件', '疑难案件']


def parse_pending_deadline(value):
    """解析前端传入的日期字符串，兼容 date / datetime / ISO 格式。"""
    if value is None or value == '':
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.time.min)

    text_value = str(value).strip()
    # 兼容前端可能出现的 ISO 时间（如 2026-03-21T00:00:00）
    if 'T' in text_value:
        text_value = text_value.split('T')[0]

    try:
        return datetime.datetime.strptime(text_value, '%Y-%m-%d')
    except ValueError:
        raise ValueError('pending_deadline 日期格式错误，应为 YYYY-MM-DD')


def serialize_case(case, include_updated_at=False):
    """统一案件序列化，避免列表/详情接口字段漂移。"""
    payload = {
        'id': case.id,
        'task_number': case.task_number,
        'stage_light': case.stage_light,
        'auth_status': case.auth_status,
        'supervise_status': case.supervise_status,
        'report_time': case.report_time.strftime('%Y-%m-%d %H:%M:%S') if case.report_time else None,
        'source': case.source,
        'major_category': case.major_category,
        'minor_category': case.minor_category,
        'problem_type': case.problem_type,
        'problem_desc': case.problem_desc,
        'address_desc': case.address_desc,
        'responsible_grid': case.responsible_grid,
        'area': case.area,
        'street': case.street,
        'community': case.community,
        'transfer_time': case.transfer_time.strftime('%Y-%m-%d %H:%M:%S') if case.transfer_time else None,
        'current_stage_time_info': case.current_stage_time_info,
        'current_stage_deadline': case.current_stage_deadline.strftime('%Y-%m-%d %H:%M:%S') if case.current_stage_deadline else None,
        'current_stage_remaining_time': case.current_stage_remaining_time,
        'area_level': case.area_level,
        'area_level_name': case.area_level_name,
        'responsible_area_name': case.responsible_area_name,
        'bundle_deadline': case.bundle_deadline.strftime('%Y-%m-%d %H:%M:%S') if case.bundle_deadline else None,
        'bundle_time_limit': case.bundle_time_limit,
        'photo_path': case.photo_path,
        'created_at': case.created_at.strftime('%Y-%m-%d %H:%M:%S') if case.created_at else None,
        'category': case.category or '',
        'status': case.status or '跟进中',
        'owner_unit': case.owner_unit or '',
        'contact_person': case.contact_person or '',
        'contact_phone': case.contact_phone or '',
        'pending_reason': case.pending_reason or '',
        'pending_deadline': case.pending_deadline.strftime('%Y-%m-%d') if case.pending_deadline else None,
        'difficult_type': case.difficult_type or '',
        'last_follow_time': case.last_follow_time.strftime('%Y-%m-%d %H:%M') if case.last_follow_time else None,
        'follow_count': case.follow_count or 0,
        'close_time': case.close_time.strftime('%Y-%m-%d %H:%M') if case.close_time else None,
        'close_remark': case.close_remark or '',
        'remark': case.remark or ''
    }
    if include_updated_at:
        payload['updated_at'] = case.updated_at.strftime('%Y-%m-%d %H:%M:%S') if case.updated_at else None
    return payload


def apply_case_category_fields(case, category, data):
    """按案件分类写入对应字段，保持现有行为不变。"""
    if category == '非我局管辖':
        case.owner_unit = data.get('owner_unit', '')
        case.contact_person = data.get('contact_person', '')
        case.contact_phone = data.get('contact_phone', '')
    elif category == '挂账案件':
        case.pending_reason = data.get('pending_reason', '')
        case.pending_deadline = parse_pending_deadline(data.get('pending_deadline'))
    elif category == '疑难案件':
        case.difficult_type = data.get('difficult_type', '')
