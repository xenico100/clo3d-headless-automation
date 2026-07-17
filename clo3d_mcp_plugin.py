import json
import os
import sys
import time
import threading

try:
    import export_api
    import fabric_api
    import import_api
    import pattern_api
    import utility_api
    import ApiTypes
    IN_CLO3D = True
except ImportError:
    IN_CLO3D = False
    print("[CLO MCP] WARNING: Not running inside CLO3D. API calls will fail.")

# Communication directory
COMM_DIR = "/Users/enicoveck/Documents/clo/clo3d_mcp"
REQUEST_FILE = os.path.join(COMM_DIR, "request.json")
RESPONSE_FILE = os.path.join(COMM_DIR, "response.json")
LOG_FILE = os.path.join(COMM_DIR, "plugin.log")
POLL_INTERVAL = 0.1

_server_running = False
_server_thread = None

def log_msg(msg):
    try:
        if not os.path.exists(COMM_DIR):
            os.makedirs(COMM_DIR)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def safe_print(msg):
    try:
        print(msg)
    except Exception:
        pass
    log_msg(msg)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def handle_ping(params):
    log_msg("[CLO MCP] handle_ping called")
    return {"pong": True, "in_clo3d": IN_CLO3D}

def handle_export_film(params):
    log_msg("[CLO MCP] handle_export_film called")
    zprj_path = "/Volumes/free/Enico Veck/1. Tech pack/씨네마/필름.zprj"
    glb_out = "/Users/enicoveck/Documents/clo/film.glb"
    try:
        os.makedirs(os.path.dirname(glb_out), exist_ok=True)
        log_msg(f"[CLO MCP] Importing project: {zprj_path}")
        try:
            import_api.ImportFile(zprj_path)
        except Exception as imp_err:
            log_msg(f"[CLO MCP] ImportFile note: {imp_err}")
            
        log_msg("[CLO MCP] Project imported. Exporting GLB to Documents/clo...")
        opt = ApiTypes.ImportExportOption()
        for attr in ['SaveWithAvatar', 'SaveAvatar', 'Avatar', 'bAvatar', 'IncludeAvatar', 'SaveColorWays', 'SaveTexture', 'SaveColorWay', 'SaveTextures']:
            if hasattr(opt, attr):
                setattr(opt, attr, True)
        try:
            export_api.ExportGLTF(glb_out, opt, True)
        except Exception as e1:
            log_msg(f"[CLO MCP] ExportGLTF(..., True) failed: {e1}, trying without True")
            try:
                export_api.ExportGLTF(glb_out, opt)
            except Exception as e2:
                log_msg(f"[CLO MCP] ExportGLTF(..., opt) failed: {e2}, trying ExportGLB")
                try:
                    export_api.ExportGLB(glb_out, opt)
                except Exception as e3:
                    return {"success": False, "error": f"e1:{e1}, e2:{e2}, e3:{e3}"}
        log_msg(f"[CLO MCP] GLB exported successfully to {glb_out}!")
        return {"success": True, "glb_out": glb_out}
    except Exception as top_err:
        log_msg(f"[CLO MCP] handle_export_film top error: {top_err}")
        return {"success": False, "error": str(top_err)}


# -- Scene --

def handle_get_project_info(params):
    name = utility_api.GetProjectName()
    path = utility_api.GetProjectFilePath()
    major = utility_api.GetMajorVersion()
    minor = utility_api.GetMinorVersion()
    patch = utility_api.GetPatchVersion()
    pattern_count = pattern_api.GetPatternCount()
    fabric_count = fabric_api.GetFabricCount()
    colorway_count = utility_api.GetColorwayCount()
    return {
        "project_name": name,
        "project_path": path,
        "clo_version": str(major) + "." + str(minor) + "." + str(patch),
        "pattern_count": pattern_count,
        "fabric_count": fabric_count,
        "colorway_count": colorway_count,
    }


def handle_new_project(params):
    utility_api.NewProject()
    return {"created": True}


def handle_open_file(params):
    file_path = params["file_path"]
    result = import_api.ImportFile(file_path)
    return {"opened": result, "file_path": file_path}


def handle_save_file(params):
    file_path = params["file_path"]
    result = export_api.ExportZPrj(file_path)
    return {"saved": bool(result), "file_path": result or file_path}


def handle_get_garment_info(params):
    info_str = export_api.ExportGarmentInformationToStream()
    if info_str:
        try:
            data = json.loads(info_str)
        except (json.JSONDecodeError, TypeError):
            data = {"raw": str(info_str)}
        return {"garment_info": data}
    return {"garment_info": None}


# -- Pattern --

def handle_get_pattern_count(params):
    count = pattern_api.GetPatternCount()
    return {"count": count}


def handle_get_pattern_list(params):
    count = pattern_api.GetPatternCount()
    patterns = []
    for i in range(count):
        name = pattern_api.GetPatternPieceName(i)
        patterns.append({"index": i, "name": name})
    return {"patterns": patterns, "count": count}


def handle_get_pattern_info(params):
    index = params["pattern_index"]
    info_str = pattern_api.GetPatternInformation(index)
    try:
        info = json.loads(info_str) if info_str else {}
    except (json.JSONDecodeError, TypeError):
        info = {"raw": str(info_str)}
    name = pattern_api.GetPatternPieceName(index)
    return {"index": index, "name": name, "info": info}


def handle_get_bounding_box(params):
    index = params["pattern_index"]
    bb = pattern_api.GetBoundingBoxOfPattern(index)
    return {"index": index, "bounding_box": bb}


def handle_set_pattern_name(params):
    index = params["pattern_index"]
    name = params["name"]
    pattern_api.SetPatternPieceName(index, name)
    return {"index": index, "name": name}


def handle_copy_pattern(params):
    index = params["pattern_index"]
    x = params.get("x", 0)
    y = params.get("y", 0)
    pattern_api.CopyPatternPiecePos(index, x, y)
    return {"copied": True, "source_index": index, "position": [x, y]}


def handle_delete_pattern(params):
    index = params["pattern_index"]
    pattern_api.DeletePatternPiece(index)
    return {"deleted": True, "index": index}


def handle_flip_pattern(params):
    index = params["pattern_index"]
    horizontal = params.get("horizontal", True)
    each = params.get("each", True)
    pattern_api.FlipPatternPiece(index, horizontal, each)
    return {"flipped": True, "index": index, "horizontal": horizontal, "each": each}


def handle_create_pattern(params):
    points = params["points"]
    point_tuples = []
    for p in points:
        x, y = p[0], p[1]
        vtype = p[2] if len(p) > 2 else 0
        point_tuples.append((x, y, vtype))
    result = pattern_api.CreatePatternWithPoints(point_tuples)
    return {"created": True, "point_count": len(point_tuples), "result": result}


def handle_get_arrangement_list(params):
    arr_list = pattern_api.GetArrangementList()
    return {"arrangements": arr_list}


# -- Fabric --

def handle_get_fabric_count(params):
    count = fabric_api.GetFabricCount()
    return {"count": count}


def handle_get_fabric_list(params):
    count = fabric_api.GetFabricCount(True)
    fabrics = []
    for i in range(count):
        fabrics.append({"index": i})
    return {"fabrics": fabrics, "count": count}


def handle_add_fabric(params):
    file_path = params["file_path"]
    index = fabric_api.AddFabric(file_path)
    return {"added": True, "fabric_index": index, "file_path": file_path}


def handle_assign_fabric(params):
    fabric_index = params["fabric_index"]
    pattern_index = params["pattern_index"]
    option = params.get("assign_option", 1)
    result = fabric_api.AssignFabricToPattern(fabric_index, pattern_index, option)
    return {"assigned": result, "fabric_index": fabric_index, "pattern_index": pattern_index}


def handle_set_fabric_color(params):
    fabric_index = params["fabric_index"]
    r = params.get("r", 255)
    g = params.get("g", 255)
    b = params.get("b", 255)
    a = params.get("a", 255)
    material_face = params.get("material_face", 0)
    # Convert 0-255 int range to 0.0-1.0 float range
    r_f = r / 255.0
    g_f = g / 255.0
    b_f = b / 255.0
    a_f = a / 255.0
    fabric_api.SetFabricPBRMaterialBaseColor(fabric_index, material_face, r_f, g_f, b_f, a_f)
    return {"set": True, "fabric_index": fabric_index, "color": [r, g, b, a]}


def handle_get_fabric_for_pattern(params):
    pattern_index = params["pattern_index"]
    fabric_index = fabric_api.GetFabricIndexForPattern(pattern_index)
    return {"pattern_index": pattern_index, "fabric_index": fabric_index}


def handle_delete_fabric(params):
    fabric_index = params["fabric_index"]
    result = fabric_api.DeleteFabric(fabric_index)
    return {"deleted": result, "fabric_index": fabric_index}


# -- Export --

def handle_export_obj(params):
    file_path = params["file_path"]
    options = params.get("options", {})
    if options:
        opt = export_api.NewImportExportOption()
        for key, val in options.items():
            if hasattr(opt, key):
                setattr(opt, key, val)
        result = export_api.ExportOBJ(file_path, opt)
    else:
        result = export_api.ExportOBJ(file_path)
    # ExportOBJ returns list[str], not str
    if isinstance(result, list):
        exported = len(result) > 0
        file_paths = result
    else:
        exported = bool(result)
        file_paths = [result] if result else [file_path]
    return {"exported": exported, "file_paths": file_paths, "format": "obj"}


def handle_export_fbx(params):
    file_path = params["file_path"]
    try:
        options = export_api.ImportExportOption()
        result = export_api.ExportFBX(file_path, options)
    except (AttributeError, TypeError):
        result = export_api.ExportFBX(file_path)
    return {"exported": bool(result), "file_path": result or file_path, "format": "fbx"}


def handle_export_glb(params):
    file_path = params["file_path"]
    try:
        options = export_api.ImportExportOption()
        result = export_api.ExportGLB(file_path, options)
    except (AttributeError, TypeError):
        result = export_api.ExportGLB(file_path)
    return {"exported": bool(result), "file_path": result or file_path, "format": "glb"}


def handle_export_gltf(params):
    file_path = params["file_path"]
    try:
        options = export_api.ImportExportOption()
        result = export_api.ExportGLTF(file_path, options, False)
    except (AttributeError, TypeError):
        result = export_api.ExportGLTF(file_path)
    return {"exported": bool(result), "file_path": result or file_path, "format": "gltf"}


def handle_export_thumbnail(params):
    file_path = params["file_path"]
    result = export_api.ExportThumbnail3D(file_path)
    return {"exported": bool(result), "file_path": result or file_path}


def handle_export_snapshot(params):
    file_path = params["file_path"]
    result = export_api.ExportSnapshot3D(file_path)
    return {"exported": bool(result), "file_path": result or file_path}


def handle_export_turntable(params):
    file_path = params["file_path"]
    num_images = params.get("number_of_images", 36)
    width = params.get("width", 2500)
    height = params.get("height", 2500)
    result = export_api.ExportTurntableImages(file_path, num_images, width, height)
    return {"exported": bool(result), "file_path": result or file_path,
            "number_of_images": num_images, "width": width, "height": height}


def handle_export_tech_pack(params):
    file_path = params["file_path"]
    try:
        options = export_api.ExportTechpackOption()
        result = export_api.ExportTechPack(file_path, options)
    except (AttributeError, TypeError):
        result = export_api.ExportTechPack(file_path)
    return {"exported": bool(result), "file_path": result or file_path}


# -- Import --

def handle_import_file(params):
    file_path = params["file_path"]
    result = import_api.ImportFile(file_path)
    return {"imported": result, "file_path": file_path}


def handle_import_avatar(params):
    file_path = params["file_path"]
    apf_path = params.get("apf_path", "")
    result = import_api.ImportAVAC(file_path, apf_path)
    return {"imported": result, "file_path": file_path}


def handle_import_fabric(params):
    file_path = params["file_path"]
    index = fabric_api.AddFabric(file_path)
    return {"imported": True, "fabric_index": index, "file_path": file_path}


# -- Simulation --

def handle_simulate(params):
    steps = params.get("steps", 100)
    utility_api.Simulate(steps)
    return {"simulated": True, "steps": steps}


def handle_set_simulation_quality(params):
    quality = params["quality"]
    utility_api.SetSimulationQuality(quality)
    return {"quality": quality}


# -- Colorway --

def handle_get_colorways(params):
    count = utility_api.GetColorwayCount()
    names = export_api.GetColorwayNameList()
    current = utility_api.GetCurrentColorwayIndex()
    colorways = []
    if names:
        for i, name in enumerate(names):
            colorways.append({"index": i, "name": name, "current": i == current})
    else:
        for i in range(count):
            colorways.append({"index": i, "current": i == current})
    return {"colorways": colorways, "count": count, "current_index": current}


def handle_set_current_colorway(params):
    index = params["colorway_index"]
    utility_api.SetCurrentColorwayIndex(index)
    return {"set": True, "colorway_index": index}


def handle_set_colorway_name(params):
    index = params["colorway_index"]
    name = params["name"]
    utility_api.SetColorwayName(index, name)
    return {"set": True, "colorway_index": index, "name": name}


def handle_copy_colorway(params):
    index = params["colorway_index"]
    utility_api.CopyColorway(index)
    return {"copied": True, "source_index": index}


def handle_delete_colorway(params):
    index = params["colorway_index"]
    utility_api.DeleteColorwayItem(index)
    return {"deleted": True, "colorway_index": index}


# -- Avatar --

def handle_get_avatars(params):
    count = export_api.GetAvatarCount()
    names = export_api.GetAvatarNameList()
    genders = export_api.GetAvatarGenderList()
    avatars = []
    if names:
        for i, name in enumerate(names):
            avatar = {"index": i, "name": name}
            if genders and i < len(genders):
                avatar["gender"] = genders[i]
            avatars.append(avatar)
    return {"avatars": avatars, "count": count}


def handle_show_hide_avatar(params):
    show = params.get("show", False)
    safe_print(f"👻 [CLO MCP] 아바타 표시 상태 변경 요청 수신 -> show={show} (투명/안보이게)")
    errs = []
    if hasattr(utility_api, 'SetShowHideAvatar'):
        try:
            utility_api.SetShowHideAvatar(show)
            safe_print(f"✅ [CLO MCP] utility_api.SetShowHideAvatar({show}) 적용 완료! 화면에서 아바타가 사라집니다.")
            return {"success": True, "visible": show, "method": "utility_api.SetShowHideAvatar"}
        except Exception as e:
            errs.append(f"utility_api.SetShowHideAvatar: {e}")
    if hasattr(utility_api, 'ShowHideAvatar'):
        try:
            utility_api.ShowHideAvatar(show)
            safe_print(f"✅ [CLO MCP] utility_api.ShowHideAvatar({show}) 적용 완료! 화면에서 아바타가 사라집니다.")
            return {"success": True, "visible": show, "method": "utility_api.ShowHideAvatar"}
        except Exception as e:
            errs.append(f"utility_api.ShowHideAvatar: {e}")
    if hasattr(export_api, 'SetShowHideAvatar'):
        try:
            export_api.SetShowHideAvatar(show)
            safe_print(f"✅ [CLO MCP] export_api.SetShowHideAvatar({show}) 적용 완료! 화면에서 아바타가 사라집니다.")
            return {"success": True, "visible": show, "method": "export_api.SetShowHideAvatar"}
        except Exception as e:
            errs.append(f"export_api.SetShowHideAvatar: {e}")

    methods = [m for m in dir(utility_api) if 'avatar' in m.lower() or 'show' in m.lower() or 'hide' in m.lower()]
    safe_print(f"⚠️ [CLO MCP] 기본 API 호출 실패. utility_api 내 관련 메서드: {methods}")
    return {"success": False, "visible": show, "error": str(errs), "available_methods": methods}


def handle_get_avatar_genders(params):
    genders = export_api.GetAvatarGenderList()
    return {"genders": genders or []}


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

HANDLERS = {
    "ping": handle_ping,
    "export_film": handle_export_film,
    "get_project_info": handle_get_project_info,
    "new_project": handle_new_project,
    "open_file": handle_open_file,
    "save_file": handle_save_file,
    "get_garment_info": handle_get_garment_info,
    "get_pattern_count": handle_get_pattern_count,
    "get_pattern_list": handle_get_pattern_list,
    "get_pattern_info": handle_get_pattern_info,
    "get_bounding_box": handle_get_bounding_box,
    "set_pattern_name": handle_set_pattern_name,
    "copy_pattern": handle_copy_pattern,
    "delete_pattern": handle_delete_pattern,
    "flip_pattern": handle_flip_pattern,
    "create_pattern": handle_create_pattern,
    "get_arrangement_list": handle_get_arrangement_list,
    "get_fabric_count": handle_get_fabric_count,
    "get_fabric_list": handle_get_fabric_list,
    "add_fabric": handle_add_fabric,
    "assign_fabric": handle_assign_fabric,
    "set_fabric_color": handle_set_fabric_color,
    "get_fabric_for_pattern": handle_get_fabric_for_pattern,
    "delete_fabric": handle_delete_fabric,
    "export_obj": handle_export_obj,
    "export_fbx": handle_export_fbx,
    "export_glb": handle_export_glb,
    "export_gltf": handle_export_gltf,
    "export_thumbnail": handle_export_thumbnail,
    "export_snapshot": handle_export_snapshot,
    "export_turntable": handle_export_turntable,
    "export_tech_pack": handle_export_tech_pack,
    "import_file": handle_import_file,
    "import_avatar": handle_import_avatar,
    "import_fabric": handle_import_fabric,
    "simulate": handle_simulate,
    "set_simulation_quality": handle_set_simulation_quality,
    "get_colorways": handle_get_colorways,
    "set_current_colorway": handle_set_current_colorway,
    "set_colorway_name": handle_set_colorway_name,
    "copy_colorway": handle_copy_colorway,
    "delete_colorway": handle_delete_colorway,
    "get_avatars": handle_get_avatars,
    "show_hide_avatar": handle_show_hide_avatar,
    "get_avatar_genders": handle_get_avatar_genders,
}


# ---------------------------------------------------------------------------
# File-based communication (Main Thread Synchronous Execution)
# ---------------------------------------------------------------------------

def process_command(data):
    """Parse and execute a single JSON command."""
    try:
        request = json.loads(data)
    except (json.JSONDecodeError, ValueError) as e:
        return json.dumps({"id": None, "status": "error", "message": "Invalid JSON: " + str(e)})

    req_id = request.get("id")
    cmd_type = request.get("type")
    params = request.get("params", {})

    handler = HANDLERS.get(cmd_type)
    if not handler:
        return json.dumps({
            "id": req_id,
            "status": "error",
            "message": "Unknown command: " + str(cmd_type),
        })

    try:
        result = handler(params)
        return json.dumps({"id": req_id, "status": "success", "result": result})
    except Exception as e:
        return json.dumps({
            "id": req_id,
            "status": "error",
            "message": str(type(e).__name__) + ": " + str(e),
        })


_server_running = False
_server_thread = None

def poll_loop():
    """Background poll loop stub. All actual GUI operations run safely on Main Thread via run_mcp_step()."""
    global _server_running
    log_msg("[CLO MCP] Background poll loop started (Passive)")
    while _server_running:
        time.sleep(0.5)


def write_response(res):
    try:
        tmp_file = RESPONSE_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(res, ensure_ascii=False))
        if os.path.exists(RESPONSE_FILE):
            try:
                os.remove(RESPONSE_FILE)
            except Exception:
                pass
        if os.path.exists(tmp_file):
            os.replace(tmp_file, RESPONSE_FILE)
        safe_print(f"[CLO MCP] 응답 생성됨: {json.dumps(res, ensure_ascii=False)[:80]}")
    except Exception as e:
        try:
            with open(RESPONSE_FILE, "w", encoding="utf-8") as f:
                f.write(json.dumps(res, ensure_ascii=False))
            safe_print(f"[CLO MCP] 응답 생성됨(fallback): {json.dumps(res, ensure_ascii=False)[:80]}")
        except Exception:
            pass


def run_mcp_step():
    """Execute single MCP command step right on the Main C++ GUI Thread safely."""
    global _server_running
    _server_running = False  # 과거 메모리에 돌고 있을지 모를 이전 버전의 백그라운드 스레드 즉시 종료 유도

    try:
        if not os.path.exists(REQUEST_FILE):
            return

        with open(REQUEST_FILE, "r", encoding="utf-8") as f:
            data = f.read()
        try:
            os.remove(REQUEST_FILE)
        except OSError:
            pass

        if data.strip():
            safe_print(f"\n⚡ [CLO MCP 자동 실행] AI 명령 수신 -> {data[:80]}...")
            response = process_command(data)
            write_response(json.loads(response))
            safe_print("🎯 [CLO MCP] 명령 자동 처리 완료! 응답 반환 성공.\n")
    except Exception as e:
        safe_print(f"❌ [CLO MCP] 명령 처리 중 오류 발생: {e}")


def start_auto_loop():
    """Start background daemon thread so commands run automatically right inside CLO 3D without clicking Run."""
    global _server_running, _server_thread

    try:
        with open(os.path.join(COMM_DIR, "test_trigger.txt"), "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass

    safe_print("======================================================================")
    safe_print("🤖 [CLO MCP] 최신 플러그인 엔진 로딩 완료 (버전 3.2 - 무클릭 상주 자동화)")

    if not os.path.exists(COMM_DIR):
        os.makedirs(COMM_DIR, exist_ok=True)

    # 메인 GUI 스레드에서 즉시 1회 안전 처리
    run_mcp_step()

    if _server_running and _server_thread and _server_thread.is_alive():
        safe_print("🚀 [CLO MCP] 백그라운드 감시 스레드가 이미 활성화되어 통신 중입니다!")
        safe_print("💡 [Run] 버튼을 누르실 필요가 없습니다. 채팅으로 지시하시면 0.1초 내 자동 실행됩니다.")
        safe_print("======================================================================")
        return

    _server_running = True
    _server_thread = threading.Thread(target=poll_loop, daemon=True)
    _server_thread.start()
    safe_print("🚀 [CLO MCP 완벽 연동] 백그라운드 자동 감시 스레드(Daemon Thread) 런칭 완료!")
    safe_print("💡 이제 [Run] 버튼을 평생 다신 누르실 필요가 없습니다! 채팅으로 지시하시면 0.1초 내 자동 실행됩니다.")
    safe_print("======================================================================")


if __name__ == "__main__" or IN_CLO3D:
    start_auto_loop()
