#!/usr/bin/env python3
"""
FlashLang Package Manager (fpm) v0.4.0
- init: создание нового пакета
- build: сборка пакета для публикации
- install: установка пакетов
- search/info/list: работа с реестром
"""

import os
import sys
import json
import shutil
import zipfile
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import urllib.request
import urllib.error


class FlashLangPackageManager:
    def __init__(self):
        self.flash_home = Path.home() / ".flang"
        self.packages_dir = self.flash_home / "packages"
        self.cache_dir = self.flash_home / "cache"
        self.config_file = self.flash_home / "config.json"
        
        self.main_registry = "https://github.com/FlashLang/flashlang_repo/raw/refs/heads/main/packages.json"
        
        self._setup_dirs()
        self._load_config()
    
    def _setup_dirs(self):
        self.flash_home.mkdir(exist_ok=True)
        self.packages_dir.mkdir(exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)
    
    def _load_config(self):
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                "registry": self.main_registry,
                "user": None,
                "token": None
            }
            self._save_config()
    
    def _save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def _fetch_json(self, url: str) -> Optional[Dict]:
        try:
            with urllib.request.urlopen(url) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            return None
    
    def init_package(self, name: str, author: str = "", description: str = ""):
        print(f"Creating new FlashLang package: {name}")
        
        project_dir = Path.cwd() / name
        
        if project_dir.exists():
            print(f"Directory '{name}' already exists")
            return False
        
        project_dir.mkdir()
        (project_dir / "src").mkdir()
        (project_dir / "lib").mkdir()
        (project_dir / "examples").mkdir()
        (project_dir / "tests").mkdir()
        
        main_content = f'''/**
 * {name} - FlashLang Package
 * {description if description else 'A FlashLang package'}
 * 
 * @author {author if author else 'Unknown'}
 * @version 0.1.0
 */

package {name};

func main() {{
    print("Hello from {name}!");
}}

func greet(name) {{
    return "Hello, " + name + "!";
}}

var VERSION = "0.1.0";
'''
        main_file = project_dir / "src" / f"{name}.flash"
        main_file.write_text(main_content, encoding='utf-8')
        
        manifest = {
            "name": name,
            "version": "0.1.0",
            "description": description if description else f"A FlashLang package: {name}",
            "main": f"src/{name}.flash",
            "author": author if author else "",
            "license": "MIT",
            "dependencies": {},
            "devDependencies": {},
            "keywords": [],
            "repository": "",
            "homepage": "",
            "flash": ">=0.3.0",
            "downloads": {}
        }
        
        manifest_file = project_dir / "fpm.json"
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        
        readme_content = f'''# {name}

{description if description else 'A FlashLang package'}

## Installation

fpm install {name}

## Usage

import {name};

var result = {name}.greet("World");
print(result);

## API

### greet(name: str) -> str
Returns a greeting message.

### VERSION: str
Current version of the package.

## License

MIT
'''
        readme = project_dir / "README.md"
        readme.write_text(readme_content, encoding='utf-8')
        
        gitignore_content = '''# Dependencies
packages/
*.pyc
__pycache__/

# Build outputs
*.fpm
.fpm-build/
dist/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
'''
        gitignore = project_dir / ".gitignore"
        gitignore.write_text(gitignore_content, encoding='utf-8')
        
        example_content = f'''/**
 * Example usage of {name}
 */

import {name};

func main() {{
    print("Testing {name} v" + {name}.VERSION);
    
    var msg = {name}.greet("FlashLang");
    print(msg);
}}

main();
'''
        example_file = project_dir / "examples" / "example.flash"
        example_file.write_text(example_content, encoding='utf-8')
        
        test_content = f'''/**
 * Tests for {name}
 */

import {name};

func test_greet() {{
    var result = {name}.greet("World");
    assert(result == "Hello, World!", "greet() failed");
}}

func test_version() {{
    assert({name}.VERSION != "", "VERSION is empty");
}}

func assert(condition, message) {{
    if (!condition) {{
        print("FAIL: " + message);
        throw message;
    }}
    print("PASS: " + message);
}}

test_version();
test_greet();

print("All tests passed!");
'''
        test_file = project_dir / "tests" / "test.flash"
        test_file.write_text(test_content, encoding='utf-8')
        
        print(f"\nCreated FlashLang package '{name}'")
        print(f"\nProject structure:")
        print(f"   {name}/")
        print(f"   ├── src/")
        print(f"   │   └── {name}.flash")
        print(f"   ├── lib/")
        print(f"   ├── examples/")
        print(f"   │   └── example.flash")
        print(f"   ├── tests/")
        print(f"   │   └── test.flash")
        print(f"   ├── fpm.json")
        print(f"   ├── README.md")
        print(f"   └── .gitignore")
        print(f"\nNext steps:")
        print(f"   cd {name}")
        print(f"   fpm install")
        print(f"   fpm run")
        print(f"   fpm test")
        print(f"   fpm build")
        
        return True
    
    def build_package(self, output_dir: str = "."):
        manifest_file = Path.cwd() / "fpm.json"
        if not manifest_file.exists():
            print("fpm.json not found. Run 'fpm init' first.")
            return False
        
        with open(manifest_file, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        name = manifest["name"]
        version = manifest["version"]
        package_name = f"{name}-{version}.fpm"
        
        print(f"Building {package_name}...")
        
        temp_dir = Path.cwd() / ".fpm-build"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()
        
        exclude_patterns = [
            ".git", ".fpm-build", "dist", "__pycache__",
            "*.pyc", "*.log", ".DS_Store", "Thumbs.db",
            "tests", "examples"
        ]
        
        print("  Copying files...")
        
        for item in Path.cwd().iterdir():
            skip = False
            for pattern in exclude_patterns:
                if item.match(pattern):
                    skip = True
                    break
            if skip:
                continue
            
            dest = temp_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, ignore=shutil.ignore_patterns(*exclude_patterns))
                print(f"     + {item.name}/")
            else:
                shutil.copy2(item, dest)
                print(f"     + {item.name}")
        
        output_path = Path.cwd() / output_dir / package_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"  Creating archive...")
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(temp_dir)
                    zipf.write(file_path, arcname)
        
        shutil.rmtree(temp_dir)
        
        print(f"  Calculating checksum...")
        sha256 = hashlib.sha256()
        with open(output_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        
        file_size = output_path.stat().st_size
        
        manifest["downloads"] = manifest.get("downloads", {})
        manifest["downloads"][version] = f"https://github.com/user/{name}/releases/download/v{version}/{package_name}"
        
        if "checksums" not in manifest:
            manifest["checksums"] = {}
        manifest["checksums"][version] = sha256.hexdigest()
        
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"\nPackage built successfully!")
        print(f"   {output_path}")
        print(f"   Size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")
        print(f"   SHA256: {sha256.hexdigest()}")
        
        return True
    
    def run_package(self, args: List[str] = None):
        manifest_file = Path.cwd() / "fpm.json"
        if not manifest_file.exists():
            print("fpm.json not found")
            return False
        
        with open(manifest_file, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        main_file = Path.cwd() / manifest.get("main", f"src/{manifest['name']}.flash")
        if not main_file.exists():
            print(f"Main file not found: {main_file}")
            return False
        
        import subprocess
        cmd = ["python", "flash.py", str(main_file)]
        if args:
            cmd.extend(args)
        
        subprocess.run(cmd)
        return True
    
    def test_package(self):
        test_file = Path.cwd() / "tests" / "test.flash"
        if not test_file.exists():
            print("No tests found (tests/test.flash)")
            return False
        
        print("Running tests...\n")
        
        import subprocess
        result = subprocess.run(["python", "flash.py", str(test_file)])
        return result.returncode == 0
    
    def search_packages(self, query: str) -> List[Dict]:
        print(f"Searching for '{query}'...")
        
        index = self._fetch_json(self.config["registry"])
        if not index:
            return []
        
        results = []
        query_lower = query.lower()
        
        for name, info in index.get("packages", {}).items():
            if (query_lower in name.lower() or
                query_lower in info.get("description", "").lower() or
                any(query_lower in kw.lower() for kw in info.get("keywords", []))):
                results.append({"name": name, **info})
        
        return results
    
    def install_package(self, package_name: str, version: Optional[str] = None):
        print(f"Installing {package_name}...")
        
        index = self._fetch_json(self.config["registry"])
        if not index:
            return False
        
        if package_name not in index.get("packages", {}):
            print(f"Package '{package_name}' not found")
            return False
        
        package_info = index["packages"][package_name]
        manifest_url = package_info.get("manifest_url")
        if not manifest_url:
            print(f"No manifest URL for '{package_name}'")
            return False
        
        print(f"  Loading manifest...")
        manifest = self._fetch_json(manifest_url)
        if not manifest:
            return False
        
        if not version:
            version = manifest.get("version")
        
        downloads = manifest.get("downloads", {})
        if version not in downloads:
            print(f"Version '{version}' not found")
            return False
        
        download_url = downloads[version]
        package_file = self.cache_dir / f"{package_name}-{version}.fpm"
        
        print(f"  Downloading {package_name}@{version}...")
        try:
            urllib.request.urlretrieve(download_url, package_file)
        except Exception as e:
            print(f"Failed to download: {e}")
            return False
        
        if "checksums" in manifest and version in manifest["checksums"]:
            sha256 = hashlib.sha256()
            with open(package_file, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256.update(chunk)
            if sha256.hexdigest() != manifest["checksums"][version]:
                print(f"SHA256 mismatch!")
                return False
        
        install_dir = self.packages_dir / package_name
        if install_dir.exists():
            shutil.rmtree(install_dir)
        install_dir.mkdir()
        
        print(f"  Extracting...")
        with zipfile.ZipFile(package_file, 'r') as zip_ref:
            zip_ref.extractall(install_dir)
        
        deps = manifest.get("dependencies", {})
        for dep_name, dep_version in deps.items():
            if not (self.packages_dir / dep_name).exists():
                print(f"  Installing dependency: {dep_name}")
                self.install_package(dep_name)
        
        print(f"Installed {package_name}@{version}")
        self._add_to_package_json(package_name, version)
        
        return True
    
    def _add_to_package_json(self, package_name: str, version: str):
        manifest_file = Path.cwd() / "fpm.json"
        if manifest_file.exists():
            with open(manifest_file, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            manifest["dependencies"][package_name] = f"^{version}"
            
            with open(manifest_file, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2)
    
    def info_package(self, package_name: str):
        index = self._fetch_json(self.config["registry"])
        if not index:
            return
        
        if package_name not in index.get("packages", {}):
            print(f"Package '{package_name}' not found")
            return
        
        info = index["packages"][package_name]
        
        print(f"\n{info['name']}")
        print(f"   Description: {info.get('description', 'N/A')}")
        print(f"   Author: {info.get('author', 'N/A')}")
        print(f"   License: {info.get('license', 'N/A')}")
        print(f"   Repository: {info.get('repository', 'N/A')}")
        
        manifest_url = info.get("manifest_url")
        if manifest_url:
            manifest = self._fetch_json(manifest_url)
            if manifest:
                print(f"   Latest version: {manifest.get('version', 'N/A')}")
                versions = list(manifest.get('downloads', {}).keys())
                if versions:
                    print(f"   Available versions: {', '.join(versions)}")
                deps = manifest.get("dependencies", {})
                if deps:
                    print(f"   Dependencies:")
                    for dep, ver in deps.items():
                        print(f"     - {dep}: {ver}")
        
        keywords = info.get("keywords", [])
        if keywords:
            print(f"   Keywords: {', '.join(keywords)}")
    
    def list_packages(self):
        packages = list(self.packages_dir.iterdir())
        
        if not packages:
            print("No packages installed")
            return
        
        print("Installed packages:")
        for pkg in packages:
            if pkg.is_dir():
                manifest_file = pkg / "fpm.json"
                if manifest_file.exists():
                    with open(manifest_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    print(f"  {data['name']}@{data['version']} - {data.get('description', '')}")
                else:
                    print(f"  {pkg.name}")


def main():
    fpm = FlashLangPackageManager()
    
    if len(sys.argv) < 2:
        print("FlashLangLang Package Manager (fpm) v0.4.0")
        print("")
        print("Usage: fpm <command> [options]")
        print("")
        print("Commands:")
        print("  init <name>           Create a new FlashLangLang package")
        print("  build                 Build package for publishing")
        print("  run                   Run the current package")
        print("  test                  Run tests")
        print("  install [pkg]         Install dependencies or specific package")
        print("  search <query>        Search for packages")
        print("  info <pkg>            Show package information")
        print("  list                  List installed packages")
        print("")
        print("Examples:")
        print("  fpm init my-package")
        print("  fpm build")
        print("  fpm search web")
        print("  fpm install web-flash")
        print("  fpm run")
        return
    
    command = sys.argv[1]
    
    try:
        if command == "init" and len(sys.argv) > 2:
            name = sys.argv[2]
            author = input("Author (optional): ").strip()
            description = input("Description (optional): ").strip()
            fpm.init_package(name, author, description)
        
        elif command == "build":
            output_dir = sys.argv[2] if len(sys.argv) > 2 else "."
            fpm.build_package(output_dir)
        
        elif command == "run":
            args = sys.argv[2:] if len(sys.argv) > 2 else None
            fpm.run_package(args)
        
        elif command == "test":
            fpm.test_package()
        
        elif command == "search" and len(sys.argv) > 2:
            results = fpm.search_packages(sys.argv[2])
            if results:
                print(f"\nFound {len(results)} packages:")
                for pkg in results:
                    print(f"  {pkg['name']} - {pkg.get('description', 'N/A')}")
            else:
                print("No packages found")
        
        elif command == "info" and len(sys.argv) > 2:
            fpm.info_package(sys.argv[2])
        
        elif command == "install":
            if len(sys.argv) > 2:
                pkg = sys.argv[2]
                version = None
                if '@' in pkg:
                    pkg, version = pkg.split('@')
                fpm.install_package(pkg, version)
            else:
                manifest_file = Path.cwd() / "fpm.json"
                if manifest_file.exists():
                    with open(manifest_file, 'r', encoding='utf-8') as f:
                        manifest = json.load(f)
                    
                    deps = manifest.get("dependencies", {})
                    if not deps:
                        print("No dependencies to install")
                    else:
                        for pkg, ver in deps.items():
                            fpm.install_package(pkg)
                else:
                    print("fpm.json not found")
        
        elif command == "list":
            fpm.list_packages()
        
        else:
            print(f"Unknown command: {command}")
    
    except KeyboardInterrupt:
        print("\nCancelled")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
