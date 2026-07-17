import datetime
import pandas as pd


def calculate_law_enforcement_score(cases):
    """计算城市综合行政执法队8个片区的考核分数和排名"""
    target_departments = [
        "执法东片区", "执法北片区", "执法南片区", "执法西片区",
        "执法中片区", "大渠执法分队", "姚孟执法分队", "安邑执法分队"
    ]
    print(f"目标统计部门：{target_departments}")
    
    team_results = []
    
    for dept_name in target_departments:
        dept_cases = [c for c in cases if c.get('处置部门') == dept_name]
        
        total = len(dept_cases)
        on_time = 0
        overdue = 0
        delay = 0
        rework = 0
        
        for case in dept_cases:
            close_time = case.get('结案时间') or case.get('handle_time')
            deadline = case.get('捆绑处置截止时间') or case.get('deadline')
            
            if close_time and deadline:
                try:
                    if isinstance(close_time, str):
                        close_time = datetime.datetime.strptime(close_time, '%Y-%m-%d %H:%M:%S')
                    if isinstance(deadline, str):
                        deadline = datetime.datetime.strptime(deadline, '%Y-%m-%d %H:%M:%S')
                    
                    if close_time < deadline:
                        on_time += 1
                    elif close_time > deadline:
                        overdue += 1
                except:
                    pass
            
            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass
            
            rework_val = case.get('返工次数') or case.get('rework')
            try:
                if rework_val is not None:
                    rework_num = int(rework_val)
                    if rework_num != 0:
                        rework += 1
            except (ValueError, TypeError):
                pass
        
        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0
        
        score = (
            (on_time_rate * 1 + overdue_rate * 0.4) * 0.8 +
            (1 - delay_rate) * 0.1 +
            (1 - rework_rate) * 0.1
        ) * 100
        
        team_results.append({
            'department': dept_name,
            'total_cases': total,
            'on_time_count': on_time,
            'overdue_count': overdue,
            'delay_count': delay,
            'rework_count': rework,
            'on_time_rate': round(on_time_rate * 100, 2),
            'overdue_rate': round(overdue_rate * 100, 2),
            'delay_rate': round(delay_rate * 100, 2),
            'rework_rate': round(rework_rate * 100, 2),
            'score': round(score, 2)
        })
        
        print(f"  {dept_name}: 总数={total}, 按期={on_time}, 超期={overdue}, 延期={delay}, 返工={rework}, 得分={score:.2f}")
    
    team_results.sort(key=lambda x: x['score'], reverse=True)
    
    for i, team in enumerate(team_results, 1):
        team['rank'] = i
    
    print(f"\n排名结果：")
    for team in team_results:
        print(f"  第{team['rank']}名：{team['department']} - {team['score']}分")
    
    total_cases = sum(t['total_cases'] for t in team_results)
    total_score = sum(t['score'] for t in team_results) / len(team_results)
    
    return {
        'total_cases': total_cases,
        'team_results': team_results,
        'score': round(total_score, 2),
        'details': {}
    }


def calculate_huanwei_score(cases):
    """计算市容环卫中心5个片区的考核分数和排名"""
    target_areas = [
        "环卫东片区", "环卫北片区", "环卫南片区",
        "环卫西片区", "环卫中片区"
    ]
    print(f"目标统计片区：{target_areas}")
    
    area_results = []
    
    for area_name in target_areas:
        area_cases = [c for c in cases if c.get('处置部门') == area_name]
        
        total = len(area_cases)
        on_time = 0
        overdue = 0
        delay = 0
        rework = 0
        
        for case in area_cases:
            close_time = case.get('结案时间') or case.get('handle_time')
            deadline = case.get('捆绑处置截止时间') or case.get('deadline')
            
            if close_time and deadline:
                try:
                    if isinstance(close_time, str):
                        close_time = datetime.datetime.strptime(close_time, '%Y-%m-%d %H:%M:%S')
                    if isinstance(deadline, str):
                        deadline = datetime.datetime.strptime(deadline, '%Y-%m-%d %H:%M:%S')
                    
                    if close_time < deadline:
                        on_time += 1
                    elif close_time > deadline:
                        overdue += 1
                except:
                    pass
            
            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass
            
            rework_val = case.get('返工次数') or case.get('rework')
            try:
                if rework_val is not None:
                    rework_num = int(rework_val)
                    if rework_num != 0:
                        rework += 1
            except (ValueError, TypeError):
                pass
        
        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0
        
        score = (
            (on_time_rate * 1 + overdue_rate * 0.4) * 0.8 +
            (1 - delay_rate) * 0.1 +
            (1 - rework_rate) * 0.1
        ) * 100
        
        area_results.append({
            'department': area_name,
            'total_cases': total,
            'on_time_count': on_time,
            'overdue_count': overdue,
            'delay_count': delay,
            'rework_count': rework,
            'on_time_rate': round(on_time_rate * 100, 2),
            'overdue_rate': round(overdue_rate * 100, 2),
            'delay_rate': round(delay_rate * 100, 2),
            'rework_rate': round(rework_rate * 100, 2),
            'score': round(score, 2)
        })
        
        print(f"  {area_name}: 总数={total}, 按期={on_time}, 超期={overdue}, 延期={delay}, 返工={rework}, 得分={score:.2f}")
    
    area_results.sort(key=lambda x: x['score'], reverse=True)
    
    for i, area in enumerate(area_results, 1):
        area['rank'] = i
    
    print(f"\n排名结果：")
    for area in area_results:
        print(f"  第{area['rank']}名：{area['department']} - {area['score']}分")
    
    total_cases = sum(a['total_cases'] for a in area_results)
    total_score = sum(a['score'] for a in area_results) / len(area_results)
    
    return {
        'total_cases': total_cases,
        'team_results': area_results,
        'score': round(total_score, 2),
        'details': {}
    }


def calculate_garden_score(cases):
    """计算园林各片区的考核得分并排名"""
    target_areas = [
        "园林东片区", "园林北片区", "园林南片区",
        "园林西片区", "园林中片区"
    ]
    print(f"目标统计片区：{target_areas}")
    
    area_results = []
    
    for area_name in target_areas:
        area_cases = [c for c in cases if c.get('处置部门') == area_name]
        
        total = len(area_cases)
        on_time = 0
        overdue = 0
        delay = 0
        rework = 0
        
        for case in area_cases:
            close_time = case.get('结案时间') or case.get('handle_time')
            deadline = case.get('捆绑处置截止时间') or case.get('deadline')
            
            if close_time and deadline:
                try:
                    if isinstance(close_time, str):
                        close_time = datetime.datetime.strptime(close_time, '%Y-%m-%d %H:%M:%S')
                    if isinstance(deadline, str):
                        deadline = datetime.datetime.strptime(deadline, '%Y-%m-%d %H:%M:%S')
                    
                    if close_time < deadline:
                        on_time += 1
                    elif close_time > deadline:
                        overdue += 1
                except:
                    pass
            
            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass
            
            rework_val = case.get('返工次数') or case.get('rework')
            try:
                if rework_val is not None:
                    rework_num = int(rework_val)
                    if rework_num != 0:
                        rework += 1
            except (ValueError, TypeError):
                pass
        
        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0
        
        score = (
            (on_time_rate * 1 + overdue_rate * 0.4) * 0.8 +
            (1 - delay_rate) * 0.1 +
            (1 - rework_rate) * 0.1
        ) * 100
        
        area_results.append({
            'department': area_name,
            'total_cases': total,
            'on_time_count': on_time,
            'overdue_count': overdue,
            'delay_count': delay,
            'rework_count': rework,
            'on_time_rate': round(on_time_rate * 100, 2),
            'overdue_rate': round(overdue_rate * 100, 2),
            'delay_rate': round(delay_rate * 100, 2),
            'rework_rate': round(rework_rate * 100, 2),
            'score': round(score, 2)
        })
        
        print(f"  {area_name}: 总数={total}, 按期={on_time}, 超期={overdue}, 延期={delay}, 返工={rework}, 得分={score:.2f}")
    
    area_results.sort(key=lambda x: x['score'], reverse=True)
    
    for i, area in enumerate(area_results, 1):
        area['rank'] = i
    
    print(f"\n排名结果：")
    for area in area_results:
        print(f"  第{area['rank']}名：{area['department']} - {area['score']}分")
    
    total_cases = sum(a['total_cases'] for a in area_results)
    total_score = sum(a['score'] for a in area_results) / len(area_results)
    
    return {
        'total_cases': total_cases,
        'team_results': area_results,
        'score': round(total_score, 2),
        'details': {}
    }


def calculate_park_score(cases):
    """计算园林各公园考核得分（排除挂账案件）"""
    target_parks = ["南风广场", "天逸公园", "体育公园", "航天公园", "圣惠公园", "禹都公园", "人民公园"]
    print(f"目标统计公园：{target_parks}")
    
    non_guazhang_cases = []
    for case in cases:
        stage = case.get('当前阶段名称') or ''
        stage_str = str(stage).strip().lower()
        if '挂账' not in stage_str:
            non_guazhang_cases.append(case)
    
    print(f"\n挂账过滤结果：")
    print(f"   - 原始案件数：{len(cases)}")
    print(f"   - 排除挂账后案件数：{len(non_guazhang_cases)}")
    print(f"   - 排除的挂账案件数：{len(cases) - len(non_guazhang_cases)}")
    
    park_results = []
    
    for park_name in target_parks:
        park_cases = [c for c in non_guazhang_cases if c.get('处置部门') == park_name]
        
        total = len(park_cases)
        on_time = 0
        overdue = 0
        delay = 0
        rework = 0
        
        for case in park_cases:
            close_time = case.get('结案时间') or case.get('handle_time')
            deadline = case.get('捆绑处置截止时间') or case.get('deadline')
            
            if close_time and deadline:
                try:
                    if isinstance(close_time, str):
                        close_time = datetime.datetime.strptime(close_time, '%Y-%m-%d %H:%M:%S')
                    if isinstance(deadline, str):
                        deadline = datetime.datetime.strptime(deadline, '%Y-%m-%d %H:%M:%S')
                    
                    if close_time < deadline:
                        on_time += 1
                    elif close_time > deadline:
                        overdue += 1
                except:
                    pass
            
            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass
            
            rework_val = case.get('返工次数') or case.get('rework')
            try:
                if rework_val is not None:
                    rework_num = int(rework_val)
                    if rework_num != 0:
                        rework += 1
            except (ValueError, TypeError):
                pass
        
        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0
        
        score = (
            (on_time_rate * 1 + overdue_rate * 0.4) * 0.8 +
            (1 - delay_rate) * 0.1 +
            (1 - rework_rate) * 0.1
        ) * 100
        
        park_results.append({
            'department': park_name,
            'total_cases': total,
            'on_time_count': on_time,
            'overdue_count': overdue,
            'delay_count': delay,
            'rework_count': rework,
            'on_time_rate': round(on_time_rate * 100, 2),
            'overdue_rate': round(overdue_rate * 100, 2),
            'delay_rate': round(delay_rate * 100, 2),
            'rework_rate': round(rework_rate * 100, 2),
            'score': round(score, 2)
        })
        
        print(f"  {park_name}: 总数={total}, 按期={on_time}, 超期={overdue}, 延期={delay}, 返工={rework}, 得分={score:.2f}")
    
    park_results.sort(key=lambda x: x['score'], reverse=True)
    
    for i, park in enumerate(park_results, 1):
        park['rank'] = i
    
    print(f"\n排名结果：")
    for park in park_results:
        print(f"  第{park['rank']}名：{park['department']} - {park['score']}分")
    
    total_cases = sum(p['total_cases'] for p in park_results)
    total_score = sum(p['score'] for p in park_results) / len(park_results)
    
    return {
        'total_cases': total_cases,
        'team_results': park_results,
        'score': round(total_score, 2),
        'details': {}
    }


def calculate_generic_score(cases):
    """其他部门的通用计算逻辑"""
    total_cases = len(cases)
    closed_cases = 0
    total_handle_hours = 0
    valid_cases = 0
    
    for case in cases:
        status = case.get('status') or case.get('状态')
        if status and '已结案' in str(status):
            closed_cases += 1
        
        create_time = case.get('create_time') or case.get('创建时间') or case.get('create_time')
        handle_time = case.get('handle_time') or case.get('处理时间') or case.get('完成时间')
        
        if create_time and handle_time:
            try:
                if isinstance(create_time, str):
                    create_time = datetime.datetime.strptime(create_time, '%Y-%m-%d %H:%M:%S')
                if isinstance(handle_time, str):
                    handle_time = datetime.datetime.strptime(handle_time, '%Y-%m-%d %H:%M:%S')
                handle_hours = (handle_time - create_time).total_seconds() / 3600
                total_handle_hours += handle_hours
                valid_cases += 1
            except Exception as e:
                print(f'解析时间失败: {e}')
    
    avg_handle_hours = total_handle_hours / valid_cases if valid_cases > 0 else 0
    
    standard_hours = 24
    
    closure_rate = (closed_cases / total_cases) * 40 if total_cases > 0 else 0
    time_score = max(0, (standard_hours - avg_handle_hours) / standard_hours * 30) if standard_hours > 0 else 0
    quality_score = 30
    
    total_score = closure_rate + time_score + quality_score
    
    return {
        'total_cases': total_cases,
        'closed_cases': closed_cases,
        'avg_handle_hours': round(avg_handle_hours, 2),
        'score': round(total_score, 2),
        'details': {
            '结案率': round(closure_rate, 2),
            '时间得分': round(time_score, 2),
            '质量得分': round(quality_score, 2)
        }
}


def calculate_law_enforcement_score_v2(cases, coefficients=None):
    """计算城市综合行政执法队8个片区的考核分数和排名（新版：使用是否超时字段判定）"""
    if coefficients is None:
        coefficients = {
            'on_time': 1.0,
            'overdue': 0.4,
            'closure_weight': 0.8,
            'delay_weight': 0.1,
            'rework_weight': 0.1
        }

    target_departments = [
        "执法东片区", "执法北片区", "执法南片区", "执法西片区",
        "执法中片区", "大渠执法分队", "姚孟执法分队", "安邑执法分队"
    ]
    print(f"目标统计部门：{target_departments}")
    print(f"使用的计分系数：{coefficients}")

    if len(cases) > 0:
        stage_vals = set()
        for c in cases:
            val = c.get('当前阶段名称')
            if val is not None and pd.notna(val):
                stage_vals.add(str(val))
        print(f"[调试] 当前阶段名称的唯一值: {sorted(stage_vals)}")

    team_results = []

    for dept_name in target_departments:
        dept_cases = [c for c in cases if c.get('处置部门') == dept_name]

        total = len(dept_cases)
        closed_cases = [c for c in dept_cases if c.get('当前阶段名称') in ['[办结]', '办结']]
        closed_count = len(closed_cases)
        closure_rate = closed_count / total if total > 0 else 0

        on_time = 0
        for case in closed_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')
            if not (pd.notna(is_overdue) and str(is_overdue).strip() != ''):
                on_time += 1

        overdue = 0
        delay = 0
        rework = 0

        for case in dept_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')

            if pd.notna(is_overdue) and str(is_overdue).strip() != '':
                overdue += 1

            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass

            rework_val = case.get('返工次数') or case.get('rework')
            try:
                if rework_val is not None:
                    rework_num = int(rework_val)
                    if rework_num != 0:
                        rework += 1
            except (ValueError, TypeError):
                pass

        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0

        score = (
            (on_time_rate * coefficients['on_time'] + overdue_rate * coefficients['overdue']) * coefficients['closure_weight'] +
            (1 - delay_rate) * coefficients['delay_weight'] +
            (1 - rework_rate) * coefficients['rework_weight']
        ) * 100

        team_results.append({
            'department': dept_name,
            'total_cases': total,
            'closed_cases': closed_count,
            'closure_rate': round(closure_rate * 100, 2),
            'on_time_count': on_time,
            'overdue_count': overdue,
            'delay_count': delay,
            'rework_count': rework,
            'on_time_rate': round(on_time_rate * 100, 2),
            'overdue_rate': round(overdue_rate * 100, 2),
            'delay_rate': round(delay_rate * 100, 2),
            'rework_rate': round(rework_rate * 100, 2),
            'score': round(score, 2)
        })

        print(f"  {dept_name}: 总数={total}, 办结={closed_count}, 按期={on_time}, 超期={overdue}, 延期={delay}, 返工={rework}, 得分={score:.2f}")
    
    team_results.sort(key=lambda x: x['score'], reverse=True)
    
    for i, team in enumerate(team_results, 1):
        team['rank'] = i
    
    print(f"\n排名结果：")
    for team in team_results:
        print(f"  第{team['rank']}名：{team['department']} - {team['score']}分")
    
    total_cases = sum(t['total_cases'] for t in team_results)
    total_score = sum(t['score'] for t in team_results) / len(team_results)
    
    return {
        'total_cases': total_cases,
        'team_results': team_results,
        'score': round(total_score, 2),
        'details': {}
    }


def calculate_huanwei_score_v2(cases, coefficients=None):
    """计算市容环卫中心5个片区的考核分数和排名（新版：使用是否超时字段判定）"""
    if coefficients is None:
        coefficients = {
            'on_time': 1.0,
            'overdue': 0.4,
            'closure_weight': 0.8,
            'delay_weight': 0.1,
            'rework_weight': 0.1
        }

    target_areas = [
        "环卫东片区", "环卫北片区", "环卫南片区",
        "环卫西片区", "环卫中片区"
    ]
    print(f"目标统计片区：{target_areas}")
    print(f"使用的计分系数：{coefficients}")

    area_results = []

    for area_name in target_areas:
        area_cases = [c for c in cases if c.get('处置部门') == area_name]

        total = len(area_cases)
        closed_cases = [c for c in area_cases if c.get('当前阶段名称') in ['[办结]', '办结']]
        closed_count = len(closed_cases)
        closure_rate = closed_count / total if total > 0 else 0

        on_time = 0
        for case in closed_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')
            if not (pd.notna(is_overdue) and str(is_overdue).strip() != ''):
                on_time += 1

        overdue = 0
        delay = 0
        rework = 0

        for case in area_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')

            if pd.notna(is_overdue) and str(is_overdue).strip() != '':
                overdue += 1

            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass

            rework_val = case.get('返工次数') or case.get('rework')
            try:
                if rework_val is not None:
                    rework_num = int(rework_val)
                    if rework_num != 0:
                        rework += 1
            except (ValueError, TypeError):
                pass

        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0

        score = (
            (on_time_rate * coefficients['on_time'] + overdue_rate * coefficients['overdue']) * coefficients['closure_weight'] +
            (1 - delay_rate) * coefficients['delay_weight'] +
            (1 - rework_rate) * coefficients['rework_weight']
        ) * 100

        detail = f"""
=== {area_name} 计算详情 ===
  总案件数: {total}
  办结案件数: {closed_count}
  结案率: {closed_count}/{total} = {closure_rate:.4f}
  按期结案: {on_time} (基于总案件数)
  超期结案: {overdue} (基于全部案件)
  延期次数: {delay} (基于全部案件)
  返工次数: {rework} (基于全部案件)
  按期率: {on_time}/{total} = {on_time_rate:.4f}
  超期率: {overdue}/{total} = {overdue_rate:.4f}
  延期率: {delay}/{total} = {delay_rate:.4f}
  返工率: {rework}/{total} = {rework_rate:.4f}
  得分计算:
    = ({on_time_rate:.4f} * {coefficients['on_time']} + {overdue_rate:.4f} * {coefficients['overdue']}) * {coefficients['closure_weight']}
      + (1 - {delay_rate:.4f}) * {coefficients['delay_weight']}
      + (1 - {rework_rate:.4f}) * {coefficients['rework_weight']}
    = {score:.4f} * 100 = {score:.2f}
"""
        print(detail)
        with open('debug.log', 'a', encoding='utf-8') as f:
            f.write(detail)

        area_results.append({
            'department': area_name,
            'total_cases': total,
            'closed_cases': closed_count,
            'closure_rate': round(closure_rate * 100, 2),
            'on_time_count': on_time,
            'overdue_count': overdue,
            'delay_count': delay,
            'rework_count': rework,
            'on_time_rate': round(on_time_rate * 100, 2),
            'overdue_rate': round(overdue_rate * 100, 2),
            'delay_rate': round(delay_rate * 100, 2),
            'rework_rate': round(rework_rate * 100, 2),
            'score': round(score, 2)
        })

        print(f"  {area_name}: 总数={total}, 办结={closed_count}, 按期={on_time}, 超期={overdue}, 延期={delay}, 返工={rework}, 得分={score:.2f}")

    area_results.sort(key=lambda x: x['score'], reverse=True)

    for i, area in enumerate(area_results, 1):
        area['rank'] = i

    print(f"\n排名结果：")
    for area in area_results:
        print(f"  第{area['rank']}名：{area['department']} - {area['score']}分")

    total_cases = sum(a['total_cases'] for a in area_results)
    total_score = sum(a['score'] for a in area_results) / len(area_results)

    return {
        'total_cases': total_cases,
        'team_results': area_results,
        'score': round(total_score, 2),
        'details': {}
    }


def calculate_garden_score_v2(cases, coefficients=None):
    """计算园林各片区的考核得分并排名（新版：使用是否超时字段判定）"""
    if coefficients is None:
        coefficients = {
            'on_time': 1.0,
            'overdue': 0.4,
            'closure_weight': 0.8,
            'delay_weight': 0.1,
            'rework_weight': 0.1
        }

    target_areas = [
        "园林东片区", "园林北片区", "园林南片区",
        "园林西片区", "园林中片区"
    ]
    print(f"目标统计片区：{target_areas}")
    print(f"使用的计分系数：{coefficients}")

    area_results = []

    for area_name in target_areas:
        area_cases = [c for c in cases if c.get('处置部门') == area_name]

        total = len(area_cases)
        closed_cases = [c for c in area_cases if c.get('当前阶段名称') in ['[办结]', '办结']]
        closed_count = len(closed_cases)
        closure_rate = closed_count / total if total > 0 else 0

        on_time = 0
        for case in closed_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')
            if not (pd.notna(is_overdue) and str(is_overdue).strip() != ''):
                on_time += 1

        overdue = 0
        delay = 0
        rework = 0

        for case in area_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')

            if pd.notna(is_overdue) and str(is_overdue).strip() != '':
                overdue += 1

            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass

            rework_val = case.get('返工次数') or case.get('rework')
            try:
                if rework_val is not None:
                    rework_num = int(rework_val)
                    if rework_num != 0:
                        rework += 1
            except (ValueError, TypeError):
                pass

        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0

        score = (
            (on_time_rate * coefficients['on_time'] + overdue_rate * coefficients['overdue']) * coefficients['closure_weight'] +
            (1 - delay_rate) * coefficients['delay_weight'] +
            (1 - rework_rate) * coefficients['rework_weight']
        ) * 100

        area_results.append({
            'department': area_name,
            'total_cases': total,
            'closed_cases': closed_count,
            'closure_rate': round(closure_rate * 100, 2),
            'on_time_count': on_time,
            'overdue_count': overdue,
            'delay_count': delay,
            'rework_count': rework,
            'on_time_rate': round(on_time_rate * 100, 2),
            'overdue_rate': round(overdue_rate * 100, 2),
            'delay_rate': round(delay_rate * 100, 2),
            'rework_rate': round(rework_rate * 100, 2),
            'score': round(score, 2)
        })

        print(f"  {area_name}: 总数={total}, 办结={closed_count}, 按期={on_time}, 超期={overdue}, 延期={delay}, 返工={rework}, 得分={score:.2f}")

    area_results.sort(key=lambda x: x['score'], reverse=True)

    for i, area in enumerate(area_results, 1):
        area['rank'] = i

    print(f"\n排名结果：")
    for area in area_results:
        print(f"  第{area['rank']}名：{area['department']} - {area['score']}分")

    total_cases = sum(a['total_cases'] for a in area_results)
    total_score = sum(a['score'] for a in area_results) / len(area_results)

    return {
        'total_cases': total_cases,
        'team_results': area_results,
        'score': round(total_score, 2),
        'details': {}
    }


def calculate_park_score_v2(cases, coefficients=None):
    """计算园林各公园考核得分（排除挂账案件）（新版：使用是否超时字段判定）"""
    if coefficients is None:
        coefficients = {
            'on_time': 1.0,
            'overdue': 0.4,
            'closure_weight': 0.8,
            'delay_weight': 0.1,
            'rework_weight': 0.1
        }

    target_parks = ["南风广场", "天逸公园", "体育公园", "航天公园", "圣惠公园", "禹都公园", "人民公园"]
    print(f"目标统计公园：{target_parks}")
    print(f"使用的计分系数：{coefficients}")

    non_guazhang_cases = []
    for case in cases:
        stage = case.get('当前阶段名称') or ''
        stage_str = str(stage).strip().lower()
        if '挂账' not in stage_str:
            non_guazhang_cases.append(case)

    print(f"\n挂账过滤结果：")
    print(f"   - 原始案件数：{len(cases)}")
    print(f"   - 排除挂账后案件数：{len(non_guazhang_cases)}")
    print(f"   - 排除的挂账案件数：{len(cases) - len(non_guazhang_cases)}")

    park_results = []

    for park_name in target_parks:
        park_cases = [c for c in non_guazhang_cases if c.get('处置部门') == park_name]

        total = len(park_cases)
        closed_cases = [c for c in park_cases if c.get('当前阶段名称') in ['[办结]', '办结']]
        closed_count = len(closed_cases)
        closure_rate = closed_count / total if total > 0 else 0

        on_time = 0
        for case in closed_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')
            if not (pd.notna(is_overdue) and str(is_overdue).strip() != ''):
                on_time += 1

        overdue = 0
        delay = 0
        rework = 0

        for case in park_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')

            if pd.notna(is_overdue) and str(is_overdue).strip() != '':
                overdue += 1

            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass

            rework_val = case.get('返工次数') or case.get('rework')
            try:
                if rework_val is not None:
                    rework_num = int(rework_val)
                    if rework_num != 0:
                        rework += 1
            except (ValueError, TypeError):
                pass

        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0

        score = (
            (on_time_rate * coefficients['on_time'] + overdue_rate * coefficients['overdue']) * coefficients['closure_weight'] +
            (1 - delay_rate) * coefficients['delay_weight'] +
            (1 - rework_rate) * coefficients['rework_weight']
        ) * 100

        park_results.append({
            'department': park_name,
            'total_cases': total,
            'closed_cases': closed_count,
            'closure_rate': round(closure_rate * 100, 2),
            'on_time_count': on_time,
            'overdue_count': overdue,
            'delay_count': delay,
            'rework_count': rework,
            'on_time_rate': round(on_time_rate * 100, 2),
            'overdue_rate': round(overdue_rate * 100, 2),
            'delay_rate': round(delay_rate * 100, 2),
            'rework_rate': round(rework_rate * 100, 2),
            'score': round(score, 2)
        })

        print(f"  {park_name}: 总数={total}, 办结={closed_count}, 按期={on_time}, 超期={overdue}, 延期={delay}, 返工={rework}, 得分={score:.2f}")

    park_results.sort(key=lambda x: x['score'], reverse=True)

    for i, park in enumerate(park_results, 1):
        park['rank'] = i

    print(f"\n排名结果：")
    for park in park_results:
        print(f"  第{park['rank']}名：{park['department']} - {park['score']}分")

    total_cases = sum(p['total_cases'] for p in park_results)
    total_score = sum(p['score'] for p in park_results) / len(park_results)

    return {
        'total_cases': total_cases,
        'team_results': park_results,
        'score': round(total_score, 2),
        'details': {}
    }
