{
  lib
, buildPythonPackage
, setuptools
, src
}:
buildPythonPackage rec {
  pname = "mount-image";
  version = "0.1.2";
  pyproject = true;

  inherit src;

  nativeBuildInputs = [ setuptools ];

  doCheck = false;
  pythonImportsCheck = [ "mount_image" ];

  meta = with lib; {
    description = "Cross-platform disk image mounting via loop devices (Linux) or hdiutil (macOS)";
    homepage = "https://github.com/MBanucu/mount-image";
    license = licenses.gpl3Only;
    maintainers = with maintainers; [ ];
  };
}
