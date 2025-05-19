from app import create_app, db
from app.models import User
import platform
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = create_app()

with app.app_context():
    db.create_all()

def set_memory_limit(max_mb=4096):
    if platform.system() != "Windows":
        import resource

        _, hard = resource.getrlimit(resource.RLIMIT_AS)
        resource.setrlimit(resource.RLIMIT_AS, (max_mb * 1024 * 1024, hard))
        print(f"Memory limit set to {max_mb} MB")

@app.route('/routes')
def list_routes():
    import urllib
    output = []
    for rule in app.url_map.iter_rules():
        methods = ','.join(rule.methods)
        line = urllib.parse.unquote(f"{rule.endpoint:40s} {methods:20s} {str(rule)}")
        output.append(line)
    return "<pre>" + "\n".join(sorted(output)) + "</pre>"

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8081)
    set_memory_limit()
