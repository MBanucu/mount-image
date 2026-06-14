{
  lib
, buildPythonPackage
, setuptools
, mount-image-sudo
, mount-image-udisks
, mount-image-guestmount
, mount-image-hdiutil
, src
}:
buildPythonPackage rec {
  pname = "mount-image";
  version = "0.3.0";
  pyproject = true;

  inherit src;

  nativeBuildInputs = [ setuptools ];
  propagatedBuildInputs = [
    mount-image-sudo
    mount-image-udisks
    mount-image-guestmount
    mount-image-hdiutil
  ];

  doCheck = false;
  pythonImportsCheck = [ "mount_image" ];

  meta = with lib; {
    description = "Cross-platform disk image mounting — strategy selector";
    homepage = "https://github.com/MBanucu/mount-image";
    license = licenses.gpl3Only;
    maintainers = with maintainers; [ ];
  };
}
