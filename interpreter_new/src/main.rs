fn main() {
    let args: Vec<String> = std::env::args().collect();
    let file_path = &args[1];
    print!("Reading file: {}", file_path);
}
