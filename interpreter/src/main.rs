use std::env;

fn main() {
  let args: Vec<String> = env::args().collect();

  if args.len() > 2 {
    println!("Usage: rmeda [script]");
  } else if args.len() > 1 {
    println!("Executing file...");
  } else {
    println!("> ");
  }
}
